"""Executes one PowerCenter session (a mapping run) against the emulated warehouse."""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import os
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from . import expr as X
from .db import Connection, qi, qualified, rewrite_sql
from .params import expand


class SessionFailed(Exception):
    def __init__(self, code, msg):
        super().__init__(f"{code} {msg}")
        self.code, self.msg = code, msg


# --------------------------------------------------------------------- conversions


def coerce(value, datatype, precision=0, scale=0, date_format=X.DEFAULT_DATE_FORMAT):
    """Convert a value into a port of the given PowerCenter datatype."""
    if value is None:
        return None
    t = datatype.lower()
    try:
        if t in ("string", "nstring", "text", "ntext", "char", "varchar", "nchar", "nvarchar"):
            s = X._to_str(value)
            return s[:precision] if precision and t in ("string", "nstring") and len(s) > precision else s
        if t in ("integer", "small integer", "bigint", "smallint", "byteint"):
            if isinstance(value, str):
                if value.strip() == "":
                    return None
                return int(Decimal(value.strip()))
            if isinstance(value, dt.datetime):
                raise X.TransformationError(f"cannot convert date to {t}")
            return int(Decimal(value))
        if t in ("decimal", "double", "real", "number", "numeric", "float"):
            if isinstance(value, str):
                if value.strip() == "":
                    return None
                value = Decimal(value.strip())
            d = Decimal(value) if not isinstance(value, Decimal) else value
            if t == "decimal" and scale is not None and precision:
                d = d.quantize(Decimal(1).scaleb(-scale), rounding=ROUND_HALF_UP)
            return d
        if t in ("date/time", "date", "timestamp", "time"):
            if isinstance(value, dt.datetime):
                return value
            if isinstance(value, dt.date):
                return dt.datetime(value.year, value.month, value.day)
            return X.parse_date(X._to_str(value), date_format)
    except (InvalidOperation, ValueError) as e:
        raise X.TransformationError(f"cannot convert [{value}] to {t}: {e}") from e
    return value


def db_value(value, f):
    """Shape a port value for a relational target column."""
    if value is None:
        return None
    t = f.datatype.lower()
    if t == "date" and isinstance(value, dt.datetime):
        return value.date()
    if t in ("char", "varchar") and not isinstance(value, str):
        return X._to_str(value)
    if t in ("integer", "smallint", "bigint", "byteint") and not isinstance(value, int):
        return int(Decimal(value))
    if t == "decimal" and isinstance(value, (int, Decimal)):
        return Decimal(value).quantize(Decimal(1).scaleb(-(f.scale or 0)), rounding=ROUND_HALF_UP)
    return value


def _default_is_error(default):
    return not default or default.upper().startswith("ERROR(")


ROW_TYPE = "__ROWTYPE__"


# --------------------------------------------------------------------- statistics


class TargetStats:
    def __init__(self, instance, table):
        self.instance, self.table = instance, table
        self.inserted = self.updated = self.deleted = 0
        self.ins_rej = self.upd_rej = self.del_rej = 0
        self.rejected = 0
        self.rows_before = self.rows_after = 0

    @property
    def applied(self):
        return self.inserted + self.updated + self.deleted

    @property
    def failed(self):
        return self.ins_rej + self.upd_rej + self.del_rej + self.rejected


class RunStats:
    def __init__(self):
        self.sources = {}
        self.targets: dict = {}
        self.transformation_errors = 0
        self.dropped_rejects = 0
        self.first_error = ("", "")

    @property
    def rows_read(self):
        return sum(self.sources.values())

    @property
    def rows_written(self):
        return sum(t.applied for t in self.targets.values())

    @property
    def rows_rejected(self):
        return sum(t.failed for t in self.targets.values()) + self.transformation_errors + self.dropped_rejects

    def error(self, code, msg):
        if not self.first_error[0]:
            self.first_error = (code, msg)


# --------------------------------------------------------------------- mapping engine


class MappingRun:
    def __init__(self, repo, session, params, process_vars, connections, log, date_format=X.DEFAULT_DATE_FORMAT):
        self.repo = repo
        self.session = session
        self.params = params
        self.pvars = process_vars
        self.connections = connections
        self.log = log
        self.date_format = date_format
        self.mapping = repo.mapping(session.folder, session.mapping)
        self.stats = RunStats()
        self.session_start = dt.datetime.now().replace(microsecond=0)
        self.mapping_params = self._mapping_params()
        self.seq_state: dict = {}
        self.lookups: dict = {}
        self.stop_on_errors = int(session.attrs.get("Stop on errors", "0") or 0)

    # -- helpers ----------------------------------------------------------

    def _mapping_params(self):
        out = {}
        for name, var in self.mapping.variables.items():
            val = None
            for k, v in self.params.items():
                if k.upper() == name.upper():
                    val = v
            if val is None:
                val = var.get("DEFAULTVALUE", "")
            out[name.upper()] = coerce(val, var.get("DATATYPE", "string"), date_format=self.date_format) if val != "" else val
        return out

    def _cctx(self, ports, aggregate=False):
        return X.CompileContext(
            port_types={p.name: p.datatype for p in ports},
            params=self.mapping_params,
            lookups=self.lookups,
            builtins={"SESSSTARTTIME": self.session_start, "$PMSessionName": self.session.name,
                      "$PMMappingName": self.mapping.name, "$PMFolderName": self.session.folder,
                      "$PMWorkflowName": self.params.get("__WORKFLOW__", "")},
            aggregate=aggregate,
        )

    def connection(self, variable_or_name, fallback=""):
        name = variable_or_name or fallback
        if name.upper() in ("$TARGET", "$SOURCE"):
            attr = "$Target connection value" if name.upper() == "$TARGET" else "$Source connection value"
            name = self.session.attrs.get(attr) or ("$DBConnection_TGT" if name.upper() == "$TARGET" else "$DBConnection_SRC")
        if name.startswith("$"):
            name = {k.upper(): v for k, v in self.params.items()}.get(name.upper(), "") or name
        key = name.upper()
        if key not in self.connections:
            raise SessionFailed("TE_7004", f"Connection [{name}] could not be resolved")
        return self.connections[key]

    def expand(self, text):
        return expand(text, self.params, self.pvars)

    def row_error(self, inst, err, row=None):
        self.stats.transformation_errors += 1
        self.stats.error("TT_11019", f"Transformation [{inst}] had an error evaluating output column: {err}")
        if self.stats.transformation_errors <= 20:
            self.log.error("TT_11019", f"There is an error in the port of transformation [{inst}]: [{err}]")
        if self.stop_on_errors and self.stats.transformation_errors >= self.stop_on_errors:
            raise SessionFailed("TM_6085", f"The error threshold [{self.stop_on_errors}] was reached")

    # -- graph ------------------------------------------------------------

    def _inputs(self):
        ins: dict = {}
        for c in self.mapping.connectors:
            ins.setdefault(c.to_instance, []).append(c)
        return ins

    def _topo(self):
        inst = self.mapping.instances
        deps = {n: set() for n in inst}
        for c in self.mapping.connectors:
            deps[c.to_instance].add(c.from_instance)
        for n, i in inst.items():
            for s in i.associated_sources:
                deps[n].add(s)
        order, done = [], set()

        def visit(n, stack=()):
            if n in done:
                return
            if n in stack:
                raise SessionFailed("TE_7017", f"Mapping [{self.mapping.name}] contains a cycle at {n}")
            for d in sorted(deps[n]):
                visit(d, stack + (n,))
            done.add(n)
            order.append(n)

        for n in inst:
            visit(n)
        return order

    def run(self):
        m = self.mapping
        inputs = self._inputs()
        order = self._topo()
        # streams: (instance, group) -> list of row contexts
        self.streams: dict = {}
        self.producer: dict = {}
        self.seq_instances = {n for n, i in m.instances.items() if i.transformation_type == "Sequence"}
        self.inputs = inputs
        for name in order:
            if self.mapping.instances[name].transformation_type == "Lookup Procedure" and name not in inputs:
                self._register_unconnected_lookup(name)
        for name in order:
            inst = m.instances[name]
            if inst.type == "SOURCE":
                continue
            if inst.type == "TARGET":
                continue
            tr = m.transformations[inst.transformation_name]
            handler = {
                "Source Qualifier": self.t_source_qualifier,
                "Expression": self.t_expression,
                "Filter": self.t_filter,
                "Lookup Procedure": self.t_lookup,
                "Aggregator": self.t_aggregator,
                "Router": self.t_router,
                "Update Strategy": self.t_update_strategy,
                "Sequence": None,
            }.get(tr.type, "unsupported")
            if handler == "unsupported":
                raise SessionFailed("TE_7001", f"Transformation type [{tr.type}] of [{name}] is not supported")
            if handler is None or (tr.type == "Lookup Procedure" and name not in inputs):
                continue
            handler(name, tr)
        targets = [t for t in (m.load_order or []) if t in m.targets]
        targets += [t for t in m.targets if t not in targets]
        writers = []
        try:
            for t in targets:
                writers.append(self.write_target(t))
        finally:
            self._save_sequences()
        return self.stats

    def _upstream_stream(self, name):
        """The row stream feeding an instance: the most downstream of its producers."""
        best = None
        for c in self.inputs.get(name, []):
            if c.from_instance in self.seq_instances:
                continue
            key = self.producer.get((c.from_instance, c.from_field))
            if key is None:
                continue
            if best is None or self._rank[key[0]] > self._rank[best[0]]:
                best = key
        if best is None:
            return []
        return self.streams[best]

    @property
    def _rank(self):
        if not hasattr(self, "_rank_cache"):
            self._rank_cache = {n: i for i, n in enumerate(self._topo())}
        return self._rank_cache

    def _bind(self, name, ports):
        """(port_upper, from_key | None, seq) for each input port of an instance."""
        src = {c.to_field.upper(): c for c in self.inputs.get(name, [])}
        out = []
        for p in ports:
            c = src.get(p.name.upper())
            if c is None:
                out.append((p.name.upper(), None, None, p))
            elif c.from_instance in self.seq_instances:
                out.append((p.name.upper(), (c.from_instance, c.from_field.upper()), c.from_instance, p))
            else:
                out.append((p.name.upper(), (c.from_instance, c.from_field.upper()), None, p))
        return out

    def _input_defaults(self, ports):
        out = {}
        for p in ports:
            if p.default and not _default_is_error(p.default):
                out[p.name.upper()] = X.compile_expr(p.default, self._cctx([]))({})
        return out

    def _read_inputs(self, ctx, binding, defaults):
        local = {}
        for pname, key, seq, port in binding:
            if key is None:
                v = None
            elif seq is not None:
                v = self._seq_value(ctx, seq, key[1])
            else:
                v = ctx.get(key)
            if v is None and pname in defaults:
                v = defaults[pname]
            local[pname] = v
        return local

    def _publish(self, name, ports, stream, group=None):
        for p in ports:
            self.producer[(name, p.name)] = (name, group)
            self.producer[(name, p.name.upper())] = (name, group)
        self.streams[(name, group)] = stream

    # -- Source Qualifier -------------------------------------------------

    def t_source_qualifier(self, name, tr):
        inst = self.mapping.instances[name]
        src_inst = inst.associated_sources[0] if inst.associated_sources else None
        if src_inst is None:
            for c in self.inputs.get(name, []):
                if self.mapping.instances[c.from_instance].type == "SOURCE":
                    src_inst = c.from_instance
        source = self.mapping.sources[src_inst]
        sq_from = {c.to_field.upper(): c.from_field for c in self.inputs.get(name, []) if c.from_instance == src_inst}
        ports = [p for p in tr.fields]
        linked = [p for p in ports if p.name.upper() in sq_from]
        if source.is_flatfile:
            raw_rows = self._read_flatfile(src_inst, source)
        else:
            raw_rows = self._read_relational(name, tr, src_inst, source, linked, sq_from)
        stream = []
        skey = [(p.name.upper(), sq_from[p.name.upper()].upper(), p) for p in linked]
        for raw in raw_rows:
            ctx = {}
            try:
                for pn, sf, p in skey:
                    ctx[(name, pn)] = coerce(raw.get(sf), p.datatype, p.precision, p.scale, self.date_format)
            except X.TransformationError as e:
                self.row_error(name, e)
                continue
            stream.append(ctx)
        self.stats.sources[src_inst] = len(stream)
        self.log.info("READER_1021", f"Source [{src_inst}]: read [{len(stream)}] rows through [{name}]")
        self._publish(name, ports, stream)

    def _read_flatfile(self, inst_name, source):
        ext = self.session.ext_for(inst_name, "READER")
        attrs = ext.attrs if ext else {}
        directory = self.expand(attrs.get("Source file directory", "$PMSourceFileDir/"))
        filename = self.expand(attrs.get("Source filename", source.name + ".dat"))
        path = os.path.join(directory, filename)
        if not os.path.exists(path):
            raise SessionFailed("FR_3000", f"Error opening file [{path}]. Operating system error message [No such file or directory].")
        ff = source.flatfile
        delim = ff.get("DELIMITERS", ",") or ","
        if delim.startswith("&#"):
            delim = chr(int(delim[2:].rstrip(";")))
        skip = int(ff.get("SKIPROWS", "0") or 0)
        quote = ff.get("QUOTE_CHARACTER", "NONE")
        self.log.info("FR_3055", f"Reading data from input source file [{path}]")
        names = [f.name.upper() for f in source.fields]
        rows = []
        with open(path, encoding="utf-8", newline="") as fh:
            reader = csv.reader(fh, delimiter=delim, quotechar='"' if quote == "DOUBLE" else ("'" if quote == "SINGLE" else "\x00"),
                                quoting=csv.QUOTE_MINIMAL if quote in ("DOUBLE", "SINGLE") else csv.QUOTE_NONE)
            for i, rec in enumerate(reader):
                if i < skip or not rec:
                    continue
                row = {}
                for j, n in enumerate(names):
                    v = rec[j] if j < len(rec) else ""
                    row[n] = None if v == "" else v
                rows.append(row)
        return rows

    def _read_relational(self, name, tr, src_inst, source, linked, sq_from):
        ext = self.session.ext_for(name, "READER") or self.session.ext_for(src_inst, "READER")
        conn = self.connection(ext.connection_variable if ext else "", ext.connection_name if ext else "")
        override = (tr.attr("Sql Query") or "").strip()
        if override:
            sql = rewrite_sql(self.expand(override), conn)
            with conn.conn.cursor() as cur:
                cur.execute(sql)
                cols = [d.name.upper() for d in cur.description]
                data = _rtrim_char(cur)
            # override columns bind positionally to the linked SQ ports
            out = []
            for rec in data:
                out.append({sq_from[p.name.upper()].upper(): rec[i] for i, p in enumerate(linked) if i < len(cols)})
            self.log.info("RR_4049", f"SQL Query issued to database : ({self.session_start:%a %b %d %H:%M:%S %Y}) [{sql}]")
            return out
        schema, table, cols = conn.resolve_table(source.owner, source.name)
        selected = [sq_from[p.name.upper()] for p in linked]
        select = ", ".join(qi(cols.get(c.upper(), c)) for c in selected)
        distinct = "DISTINCT " if tr.attr("Select Distinct", "NO") == "YES" else ""
        sql = f"SELECT {distinct}{select} FROM {qualified(schema, table)}"
        flt = self.expand(tr.attr("Source Filter") or "").strip()
        if flt:
            sql += " WHERE " + rewrite_sql(flt, conn)
        sorted_ports = int(tr.attr("Number Of Sorted Ports", "0") or 0)
        if sorted_ports:
            sql += " ORDER BY " + ", ".join(qi(cols.get(c.upper(), c)) for c in selected[:sorted_ports])
        self.log.info("RR_4049", f"SQL Query issued to database : ({self.session_start:%a %b %d %H:%M:%S %Y}) [{sql}]")
        with conn.conn.cursor() as cur:
            cur.execute(sql)
            data = _rtrim_char(cur)
        keys = [c.upper() for c in selected]
        return [dict(zip(keys, rec)) for rec in data]

    # -- Expression -------------------------------------------------------

    def _compile_ports(self, tr, ports, aggregate=False):
        cctx = self._cctx(tr.fields, aggregate)
        compiled = []
        for p in ports:
            text = p.expression if p.expression else p.name
            try:
                fn = X.compile_expr(text, cctx)
            except X.ExpressionError as e:
                raise SessionFailed("TE_7002", f"Transformation [{tr.name}] port [{p.name}] parse error: {e}") from e
            default = None
            if not _default_is_error(p.default):
                default = X.compile_expr(p.default, self._cctx([]))({})
            compiled.append((p, fn, default))
        return compiled, cctx

    def t_expression(self, name, tr):
        in_ports = [p for p in tr.fields if p.is_input]
        var_ports = [p for p in tr.fields if p.is_variable]
        out_ports = [p for p in tr.fields if p.is_output and not p.is_input]
        io_ports = [p for p in tr.fields if p.is_output and p.is_input]
        binding = self._bind(name, in_ports)
        defaults = self._input_defaults(in_ports)
        vcomp, _ = self._compile_ports(tr, var_ports)
        ocomp, _ = self._compile_ports(tr, out_ports)
        variables = {p.name.upper(): _initial(p.datatype) for p in var_ports}
        stream = self._upstream_stream(name)
        out = []
        for ctx in stream:
            local = self._read_inputs(ctx, binding, defaults)
            local.update(variables)
            try:
                for p, fn, default in vcomp:
                    local[p.name.upper()] = coerce(fn(local), p.datatype, p.precision, p.scale, self.date_format)
                for p in var_ports:
                    variables[p.name.upper()] = local[p.name.upper()]
                for p, fn, default in ocomp:
                    try:
                        v = coerce(fn(local), p.datatype, p.precision, p.scale, self.date_format)
                    except X.TransformationError:
                        if default is None:
                            raise
                        v = default
                    ctx[(name, p.name.upper())] = v
                for p in io_ports:
                    ctx[(name, p.name.upper())] = local[p.name.upper()]
            except X.TransformationError as e:
                self.row_error(name, e)
                continue
            out.append(ctx)
        if len(out) != len(stream):
            stream[:] = out
        self._publish(name, tr.fields, stream)

    # -- Filter -----------------------------------------------------------

    def t_filter(self, name, tr):
        ports = [p for p in tr.fields if p.is_input]
        binding = self._bind(name, ports)
        defaults = self._input_defaults(ports)
        cond = X.compile_expr(tr.attr("Filter Condition") or "TRUE", self._cctx(tr.fields))
        out = []
        for ctx in self._upstream_stream(name):
            local = self._read_inputs(ctx, binding, defaults)
            try:
                keep = X.truthy(cond(local))
            except X.TransformationError as e:
                self.row_error(name, e)
                continue
            if keep:
                for p in ports:
                    ctx[(name, p.name.upper())] = local[p.name.upper()]
                out.append(ctx)
        self._publish(name, tr.fields, out)

    # -- Lookup -----------------------------------------------------------

    def _lookup_cache(self, name, tr):
        conn = self.connection(self._session_conn_var(name) or tr.attr("Connection Information") or "$Target")
        lkp_ports = [p for p in tr.fields if p.is_lookup]
        cond_text = tr.attr("Lookup condition")
        conds = []
        for part in [c.strip() for c in _split_and(cond_text)]:
            for op in ("<=", ">=", "!=", "<>", "=", "<", ">"):
                if op in part:
                    left, right = [s.strip() for s in part.split(op, 1)]
                    conds.append((left.upper(), "<>" if op == "!=" else op, right.upper()))
                    break
        override = (tr.attr("Lookup Sql Override") or "").strip()
        sel_ports = [p.name for p in lkp_ports]
        eq_cols = [c[0] for c in conds if c[1] == "="]
        if override:
            sql = rewrite_sql(self.expand(override), conn)
        else:
            table_ref = tr.attr("Lookup table name")
            owner = ""
            if "." in table_ref:
                owner, table_ref = table_ref.split(".", 1)
            schema, table, cols = conn.resolve_table(owner, table_ref)
            sql = "SELECT " + ", ".join(f"{qi(cols.get(c.upper(), c))} AS {qi(c.upper())}" for c in sel_ports)
            sql += f" FROM {qualified(schema, table)}"
            flt = self.expand(tr.attr("Lookup Source Filter") or "").strip()
            if flt:
                sql += " WHERE " + rewrite_sql(flt, conn)
            order = [c[0] for c in conds]
            if order:
                sql += " ORDER BY " + ", ".join(qi(cols.get(c, c)) for c in dict.fromkeys(order))
        self.log.info("TT_11021", f"Lookup table row count : building cache for [{name}] with [{sql}]")
        with conn.conn.cursor() as cur:
            cur.execute(sql)
            names = [d.name.upper() for d in cur.description]
            data = _rtrim_char(cur)
        types = {p.name.upper(): p for p in lkp_ports}
        cache: dict = {}
        for rec in data:
            row = {}
            for n, v in zip(names, rec):
                p = types.get(n)
                row[n] = coerce(v, p.datatype, p.precision, p.scale) if p else v
            key = tuple(_norm_key(row.get(c)) for c in eq_cols)
            cache.setdefault(key, []).append(row)
        self.log.info("TT_11185", f"Lookup [{name}]: cache built with [{len(data)}] rows")
        policy = tr.attr("Lookup policy on multiple match", "Use First Value") or "Use First Value"
        other = [c for c in conds if c[1] != "="]
        eq_inputs = [c[2] for c in conds if c[1] == "="]

        def probe(local):
            key = tuple(_norm_key(local.get(c)) for c in eq_inputs)
            if any(k is None for k in key):
                return None
            cands = cache.get(key, [])
            if other:
                cands = [r for r in cands if all(_cmp(r.get(lc), op, local.get(ic)) for lc, op, ic in other)]
            if not cands:
                return None
            if policy == "Use Last Value":
                return cands[-1]
            if policy == "Report Error" and len(cands) > 1:
                raise X.TransformationError(f"TE_7083 Lookup [{name}] found multiple matches")
            return cands[0]

        return probe

    def _session_conn_var(self, name):
        ext = self.session.ext_for(name)
        if ext is not None:
            return ext.connection_variable or ext.connection_name
        return ""

    def t_lookup(self, name, tr):
        in_ports = [p for p in tr.fields if p.is_input]
        out_ports = [p for p in tr.fields if p.is_output and not p.is_input]
        binding = self._bind(name, in_ports)
        defaults = self._input_defaults(in_ports)
        probe = self._lookup_cache(name, tr)
        stream = self._upstream_stream(name)
        for ctx in stream:
            local = self._read_inputs(ctx, binding, defaults)
            try:
                hit = probe(local)
            except X.TransformationError as e:
                self.row_error(name, e)
                hit = None
            for p in in_ports:
                if p.is_output:
                    ctx[(name, p.name.upper())] = local[p.name.upper()]
            for p in out_ports:
                ctx[(name, p.name.upper())] = None if hit is None else hit.get(p.name.upper())
        self._publish(name, tr.fields, stream)

    def _register_unconnected_lookup(self, name):
        tr = self.mapping.transformations[self.mapping.instances[name].transformation_name]
        in_ports = [p for p in tr.fields if p.is_input]
        ret = [p for p in tr.fields if p.is_return]
        holder = {}

        def call(*args):
            if "probe" not in holder:
                holder["probe"] = self._lookup_cache(name, tr)
            local = {p.name.upper(): a for p, a in zip(in_ports, args)}
            hit = holder["probe"](local)
            return None if hit is None or not ret else hit.get(ret[0].name.upper())

        self.lookups[name.upper()] = call

    # -- Aggregator -------------------------------------------------------

    def t_aggregator(self, name, tr):
        in_ports = [p for p in tr.fields if p.is_input]
        group_by = [p.name.upper() for p in tr.fields if p.expressiontype == "GROUPBY"]
        out_ports = [p for p in tr.fields if p.is_output and not p.is_input]
        io_ports = [p for p in tr.fields if p.is_output and p.is_input]
        binding = self._bind(name, in_ports)
        defaults = self._input_defaults(in_ports)
        comp, cctx = self._compile_ports(tr, out_ports, aggregate=True)
        specs = X.aggregate_specs(cctx)
        groups: dict = {}
        for ctx in self._upstream_stream(name):
            local = self._read_inputs(ctx, binding, defaults)
            key = tuple(_norm_key(local[g]) for g in group_by)
            g = groups.get(key)
            if g is None:
                g = groups[key] = [{slot: X.AggState(spec) for slot, spec in specs}, None]
            try:
                for st in g[0].values():
                    st.add(local)
            except X.TransformationError as e:
                self.row_error(name, e)
                continue
            g[1] = local
        out = []
        for states, last in groups.values():
            if last is None:
                continue
            local = dict(last)
            local["__AGG__"] = {slot: st.result() for slot, st in states.items()}
            ctx = {}
            try:
                for p, fn, default in comp:
                    ctx[(name, p.name.upper())] = coerce(fn(local), p.datatype, p.precision, p.scale)
                for p in io_ports:
                    ctx[(name, p.name.upper())] = local[p.name.upper()]
            except X.TransformationError as e:
                self.row_error(name, e)
                continue
            out.append(ctx)
        self.log.info("TT_11031", f"Aggregator [{name}]: [{len(out)}] groups produced")
        self._publish(name, tr.fields, out)

    # -- Router -----------------------------------------------------------

    def t_router(self, name, tr):
        in_ports = [p for p in tr.fields if p.group == "INPUT" or (p.is_input and not p.group)]
        binding = self._bind(name, in_ports)
        defaults = self._input_defaults(in_ports)
        cctx = self._cctx(in_ports)
        groups = [g for g in tr.groups if g.get("TYPE", "").startswith("OUTPUT")]
        user = [(g["NAME"], X.compile_expr(g.get("EXPRESSION") or "FALSE", cctx)) for g in groups if g.get("TYPE") == "OUTPUT"]
        default = [g["NAME"] for g in groups if g.get("TYPE") == "OUTPUT/DEFAULT"]
        out_fields = {}
        for p in tr.fields:
            if p.group and p.group != "INPUT":
                out_fields.setdefault(p.group, []).append(p)
        streams = {g["NAME"]: [] for g in groups}
        for ctx in self._upstream_stream(name):
            local = self._read_inputs(ctx, binding, defaults)
            matched = []
            try:
                for gname, cond in user:
                    if X.truthy(cond(local)):
                        matched.append(gname)
            except X.TransformationError as e:
                self.row_error(name, e)
                continue
            if not matched:
                matched = default
            for gname in matched:
                nctx = dict(ctx)
                for p in out_fields.get(gname, []):
                    nctx[(name, p.name.upper())] = local.get((p.ref_field or p.name).upper())
                streams[gname].append(nctx)
        for gname, rows in streams.items():
            self._publish(name, out_fields.get(gname, []), rows, gname)
            self.log.info("TT_11033", f"Router [{name}] group [{gname}]: [{len(rows)}] rows")

    # -- Update Strategy --------------------------------------------------

    def t_update_strategy(self, name, tr):
        ports = [p for p in tr.fields if p.is_input]
        binding = self._bind(name, ports)
        defaults = self._input_defaults(ports)
        strategy = X.compile_expr(tr.attr("Update Strategy Expression") or "DD_INSERT", self._cctx(tr.fields))
        forward = (tr.attr("Forward Rejected Rows", "YES") or "YES") == "YES"
        out = []
        for ctx in self._upstream_stream(name):
            local = self._read_inputs(ctx, binding, defaults)
            try:
                rt = strategy(local)
            except X.TransformationError as e:
                self.row_error(name, e)
                continue
            rt = X.DD_INSERT if rt is None else int(rt)
            for p in ports:
                ctx[(name, p.name.upper())] = local[p.name.upper()]
            ctx[ROW_TYPE] = rt
            if rt == X.DD_REJECT and not forward:
                self.stats.dropped_rejects += 1
                continue
            out.append(ctx)
        self._publish(name, tr.fields, out)

    # -- Sequence Generator -----------------------------------------------

    def _seq_file(self):
        d = self.expand("$PMStorageDir")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, "sequence_values.json")

    def _seq_value(self, ctx, seq, field):
        key = (seq, "NEXTVAL")
        if key not in ctx:
            st = self.seq_state.get(seq)
            if st is None:
                tr = self.mapping.transformations[self.mapping.instances[seq].transformation_name]
                saved = {}
                if os.path.exists(self._seq_file()):
                    with open(self._seq_file(), encoding="utf-8") as fh:
                        saved = json.load(fh)
                skey = f"{self.session.folder}.{self.mapping.name}.{seq}"
                start = int(tr.attr("Start Value", "0") or 0)
                cur = int(tr.attr("Current Value", "1") or 1)
                if tr.attr("Reset", "NO") != "YES" and skey in saved:
                    cur = saved[skey]
                st = self.seq_state[seq] = {
                    "key": skey, "cur": cur, "inc": int(tr.attr("Increment By", "1") or 1),
                    "end": int(tr.attr("End Value", "9223372036854775807") or 9223372036854775807),
                    "start": start, "cycle": tr.attr("Cycle", "NO") == "YES", "reset": tr.attr("Reset", "NO") == "YES",
                }
            val = st["cur"]
            if val > st["end"]:
                if not st["cycle"]:
                    raise SessionFailed("TT_11009", f"Sequence Transformation [{seq}]: Current value [{val}] exceeds end value")
                val = st["start"]
            st["cur"] = val + st["inc"]
            ctx[key] = val
            ctx[(seq, "CURRVAL")] = val + st["inc"]
        return ctx[(seq, field.upper())]

    def _save_sequences(self):
        if not self.seq_state:
            return
        path = self._seq_file()
        saved = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                saved = json.load(fh)
        for st in self.seq_state.values():
            if not st["reset"]:
                saved[st["key"]] = st["cur"]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(saved, fh, indent=2, sort_keys=True)

    # -- Writer -----------------------------------------------------------

    def write_target(self, inst_name):
        target = self.mapping.targets[inst_name]
        ext = self.session.ext_for(inst_name, "WRITER")
        attrs = ext.attrs if ext else {}
        conn: Connection = self.connection(ext.connection_variable if ext else "", ext.connection_name if ext else "")
        owner = self.expand(attrs.get("Table Name Prefix", "")) or conn.default_database
        table_name = self.expand(attrs.get("Target Table Name", "")) or target.name
        schema, table, cols = conn.resolve_table(owner, table_name)
        stats = self.stats.targets[inst_name] = TargetStats(inst_name, f"{schema}.{table}")
        incoming = {c.to_field.upper(): c for c in self.inputs.get(inst_name, [])}
        fields = [f for f in target.fields if f.name.upper() in incoming]
        stream = self._upstream_stream(inst_name)
        keys = [k.upper() for k in target.keys]
        treat = self.session.attrs.get("Treat source rows as", "Insert")
        default_type = {"Insert": X.DD_INSERT, "Update": X.DD_UPDATE, "Delete": X.DD_DELETE}.get(treat, X.DD_INSERT)
        allow = {
            X.DD_INSERT: attrs.get("Insert", "YES") == "YES",
            X.DD_UPDATE: attrs.get("Update as Update", "YES") == "YES" or attrs.get("Update else Insert", "NO") == "YES",
            X.DD_DELETE: attrs.get("Delete", "YES") == "YES",
        }
        upd_else_ins = attrs.get("Update else Insert", "NO") == "YES"
        bad_dir = self.expand(attrs.get("Reject file directory", "$PMBadFileDir/"))
        bad_name = self.expand(attrs.get("Reject filename", inst_name.lower() + "1.bad"))
        os.makedirs(bad_dir, exist_ok=True)
        bad_path = os.path.join(bad_dir, bad_name)
        bad = open(bad_path, "w", encoding="utf-8")
        cur = conn.conn.cursor()
        pre_sql = self.expand(attrs.get("Pre SQL", "") or "").strip()
        if pre_sql:
            for stmt in [x for x in pre_sql.split(";") if x.strip()]:
                cur.execute(rewrite_sql(stmt, conn))
                self.log.info("WRT_8251", f"Pre SQL issued for target [{inst_name}]: [{stmt.strip()}] affected [{cur.rowcount}] rows")
        cur.execute(f"SELECT count(*) FROM {qualified(schema, table)}")
        stats.rows_before = cur.fetchone()[0]
        if attrs.get("Truncate target table option", "NO") == "YES":
            cur.execute(f"DELETE FROM {qualified(schema, table)}")
            self.log.info("WRT_8124", f"Target Table {table} :Truncated using DELETE FROM")
        phys = [cols.get(f.name.upper(), f.name) for f in fields]
        ins_sql = f"INSERT INTO {qualified(schema, table)} ({', '.join(qi(c) for c in phys)}) VALUES ({', '.join(['%s'] * len(phys))})"
        nonkey = [f for f in fields if f.name.upper() not in keys]
        keyf = [f for f in fields if f.name.upper() in keys]
        upd_sql = (f"UPDATE {qualified(schema, table)} SET " + ", ".join(f"{qi(cols.get(f.name.upper(), f.name))} = %s" for f in nonkey)
                   + " WHERE " + " AND ".join(f"{qi(cols.get(f.name.upper(), f.name))} = %s" for f in keyf)) if keyf and nonkey else None
        del_sql = (f"DELETE FROM {qualified(schema, table)} WHERE "
                   + " AND ".join(f"{qi(cols.get(f.name.upper(), f.name))} = %s" for f in keyf)) if keyf else None

        def values(ctx):
            vals = []
            for f in fields:
                c = incoming[f.name.upper()]
                if c.from_instance in self.seq_instances:
                    v = self._seq_value(ctx, c.from_instance, c.from_field)
                else:
                    v = ctx.get((c.from_instance, c.from_field.upper()))
                vals.append(db_value(v, f))
            return vals

        def reject(rt, vals, reason=""):
            bad.write(",".join([str(rt)] + [f"D,{'' if v is None else v}" for v in vals]) + "\n")
            if reason and stats.failed <= 20:
                self.log.error("WRT_8229", f"Database errors occurred: {reason}")
                self.stats.error("WRT_8229", reason)

        inserts = []

        def flush_inserts():
            if not inserts:
                return
            sp = conn.conn.transaction()
            try:
                with sp:
                    buf = io.StringIO()
                    for vals in inserts:
                        buf.write("\t".join(_copy_text(v) for v in vals) + "\n")
                    with cur.copy(f"COPY {qualified(schema, table)} ({', '.join(qi(c) for c in phys)}) FROM STDIN") as cp:
                        cp.write(buf.getvalue())
                stats.inserted += len(inserts)
            except Exception:
                for vals in inserts:
                    try:
                        with conn.conn.transaction():
                            cur.execute(ins_sql, vals)
                        stats.inserted += 1
                    except Exception as e:  # noqa: BLE001 - database reject
                        stats.ins_rej += 1
                        reject(X.DD_INSERT, vals, str(e).splitlines()[0])
            inserts.clear()

        for ctx in stream:
            rt = ctx.get(ROW_TYPE, default_type) if treat == "Data driven" else default_type
            vals = values(ctx)
            if rt == X.DD_REJECT:
                stats.rejected += 1
                reject(rt, vals)
                continue
            if not allow.get(rt, False):
                stats.rejected += 1
                reject(rt, vals)
                continue
            if rt == X.DD_INSERT:
                inserts.append(vals)
                if len(inserts) >= 5000:
                    flush_inserts()
                continue
            flush_inserts()
            if rt == X.DD_UPDATE:
                if upd_sql is None:
                    raise SessionFailed("WRT_8049", f"Target table [{table}] has no keys specified for update")
                byname = dict(zip([f.name.upper() for f in fields], vals))
                try:
                    with conn.conn.transaction():
                        cur.execute(upd_sql, [byname[f.name.upper()] for f in nonkey] + [byname[f.name.upper()] for f in keyf])
                        n = cur.rowcount
                    if n == 0 and upd_else_ins:
                        inserts.append(vals)
                    else:
                        stats.updated += n
                except Exception as e:  # noqa: BLE001
                    stats.upd_rej += 1
                    reject(rt, vals, str(e).splitlines()[0])
            elif rt == X.DD_DELETE:
                if del_sql is None:
                    raise SessionFailed("WRT_8049", f"Target table [{table}] has no keys specified for delete")
                byname = dict(zip([f.name.upper() for f in fields], vals))
                try:
                    with conn.conn.transaction():
                        cur.execute(del_sql, [byname[f.name.upper()] for f in keyf])
                        stats.deleted += cur.rowcount
                except Exception as e:  # noqa: BLE001
                    stats.del_rej += 1
                    reject(rt, vals, str(e).splitlines()[0])
        flush_inserts()
        cur.execute(f"SELECT count(*) FROM {qualified(schema, table)}")
        stats.rows_after = cur.fetchone()[0]
        self.log.info("WRT_8167", f"Target table [{schema}.{table}] (instance [{inst_name}]) row count before load [{stats.rows_before}], after load [{stats.rows_after}]")
        bad.close()
        if os.path.getsize(bad_path) == 0:
            os.remove(bad_path)
        return stats


_BPCHAR_OID = 1042


def _rtrim_char(cur):
    """Fetch all rows, dropping CHAR(n) pad blanks the way the reader does unless TreatCHARasCHARonRead is set."""
    pad = [i for i, d in enumerate(cur.description) if d.type_code == _BPCHAR_OID]
    rows = cur.fetchall()
    if not pad:
        return rows
    out = []
    for r in rows:
        r = list(r)
        for i in pad:
            if r[i] is not None:
                r[i] = r[i].rstrip(" ")
        out.append(tuple(r))
    return out


def _copy_text(v):
    if v is None:
        return "\\N"
    if isinstance(v, (dt.datetime, dt.date)):
        return v.isoformat(sep=" ") if isinstance(v, dt.datetime) else v.isoformat()
    s = X._to_str(v)
    return s.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


def _initial(datatype):
    t = datatype.lower()
    if "date" in t:
        return dt.datetime(1753, 1, 1)
    if "string" in t or "char" in t or "text" in t:
        return ""
    return 0


def _norm_key(v):
    if isinstance(v, Decimal) and v == v.to_integral_value():
        return int(v)
    return v


def _cmp(a, op, b):
    if a is None or b is None:
        return False
    a, b = X._cmp_norm(a, b)
    return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b, "<>": a != b}[op]


def _split_and(text):
    import re as _re

    return [p for p in _re.split(r"\s+AND\s+", text or "", flags=_re.IGNORECASE) if p.strip()]
