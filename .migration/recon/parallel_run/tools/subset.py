import json,sys
src,unit,out=sys.argv[1:4]
d=json.load(open(src)); d["collections"]=[c for c in d["collections"] if c.get("unit")==unit]
json.dump(d,open(out,"w"),indent=2); print(out,[c["collection"] for c in d["collections"]])
