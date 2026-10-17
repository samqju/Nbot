from pathlib import Path
import pandas as pd
folder=Path("/freqtrade/work/user_data/models/nbot-v6-m1-all25-20261016/backtesting_predictions")
for p in sorted(folder.glob("*.feather"))[:3]:
 d=pd.read_feather(p)
 print("FILE",p.name,"shape",d.shape,"cols",list(d.columns),"types",d.dtypes.astype(str).to_dict())
 print("PREVIEW",d.head(2).to_dict(orient="records"))
 print("PREDICT_COUNTS",d["do_predict"].value_counts().to_dict() if "do_predict" in d else "none")
