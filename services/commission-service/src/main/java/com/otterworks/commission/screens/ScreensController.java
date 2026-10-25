package com.otterworks.commission.screens;

import java.math.BigDecimal;
import java.util.List;
import java.util.Set;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

import jakarta.servlet.http.HttpServletResponse;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.server.ResponseStatusException;

import com.otterworks.commission.common.Backend;

/** Read-only Commission Pay screens: agent commission statement and rate history. */
@Controller
@RequestMapping("/screens")
public class ScreensController {

    private static final Pattern PERIOD = Pattern.compile("\\d{4}-(0[1-9]|1[0-2])");

    private final ScreensRepository repo;
    private final Backend backend;

    public ScreensController(ScreensRepository repo, Backend backend) {
        this.repo = repo;
        this.backend = backend;
    }

    @GetMapping("/statement")
    public String statement(@RequestParam long agent, @RequestParam String period, Model model) {
        List<ScreensRepository.StatementRow> rows = common(agent, period, model);
        model.addAttribute("rows", rows);
        model.addAttribute("total", Amounts.format(Amounts.total(rows)));
        return "screens/statement";
    }

    @GetMapping("/rates")
    public String rates(@RequestParam long agent, @RequestParam String period, Model model) {
        List<ScreensRepository.StatementRow> rows = common(agent, period, model);
        Set<Long> used = rows.stream().map(ScreensRepository.StatementRow::rateId).collect(Collectors.toSet());
        model.addAttribute("rates", repo.rateHistory(agent));
        model.addAttribute("usedRateIds", used);
        return "screens/rates";
    }

    private List<ScreensRepository.StatementRow> common(long agent, String period, Model model) {
        if (!PERIOD.matcher(period).matches()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "period must be YYYY-MM, got " + period);
        }
        ScreensRepository.Agent a = repo.findAgent(agent)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Unknown agent: " + agent));
        model.addAttribute("agent", a);
        model.addAttribute("period", period);
        model.addAttribute("backend", backend.kind().name());
        model.addAttribute("database", repo.database());
        model.addAttribute("fmt", AmountsView.INSTANCE);
        return repo.statement(agent, period);
    }

    @ExceptionHandler(ResponseStatusException.class)
    public String error(ResponseStatusException e, Model model, HttpServletResponse response) {
        response.setStatus(e.getStatusCode().value());
        model.addAttribute("status", e.getStatusCode().value());
        model.addAttribute("message", e.getReason());
        model.addAttribute("backend", backend.kind().name());
        return "screens/error";
    }

    /** Template-side access to {@link Amounts#format}. */
    public static final class AmountsView {
        static final AmountsView INSTANCE = new AmountsView();

        public String money(BigDecimal v) {
            return Amounts.format(v);
        }
    }
}
