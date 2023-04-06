import pandas as pd
import argparse
import datetime
from tqdm import tqdm

# 言語モデルのファインチューニング用にデータを整形する

def concatenate(df, send_type = "text", timedelta = datetime.timedelta(minutes=30)):
  last_timestamp = datetime.datetime(1970, 1, 1)
  rows = []
  for index,row in tqdm(df.iterrows()):
    if index == 0:
      rows.append({
        "name": row["name"],
        "timestamp": row["timestamp"],
        "content": row["content"],
        "send_type": row["send_type"]
      })
      last_timestamp  = row["timestamp"]
    elif row["name"] == rows[-1]["name"] and \
      row["send_type"] == send_type and \
      row["send_type"] == rows[-1]["send_type"] and \
      row["timestamp"] - last_timestamp < timedelta:
      rows[-1]["content"] += ("<pbr>"+row["content"])
      last_timestamp = row["timestamp"]
    else:
      rows.append({
        "name": row["name"],
        "timestamp": row["timestamp"],
        "content": row["content"],
        "send_type": row["send_type"]
      })
  return pd.DataFrame(rows)

def getArgs():
  parser = argparse.ArgumentParser()
  parser.add_argument("-i", "--input", type=str, help="input file")
  parser.add_argument("--sep", type=str, help="separator", default="\t")
  parser.add_argument("-o", "--output", type=str, help="output file")
  args = parser.parse_args()
  return args

def get_turn(df, send_type = "text", timedelta = datetime.timedelta(minutes=30)):
  rows = []
  for (i1,r1), (i2, r2) in tqdm(zip(df[:-1].iterrows(), df[1:].iterrows())):
    if r1["send_type"] != send_type or r2["send_type"] != send_type: continue
    if r1["name"] == r2["name"]: continue
    if r1["timestamp"] - r2["timestamp"] > timedelta: continue

    rows.append({
      "name": r1["name"],
      "timestamp": r1["timestamp"],
      "content": r1["content"],
      "next_name": r2["name"],
      "next_timestamp": r2["timestamp"],
      "next_content": r2["content"]
    })
  
  return pd.DataFrame(rows)




if __name__=="__main__":
  args = getArgs()
  df = pd.read_csv(args.input,sep=args.sep)
  #df = df[:1000]
  df["timestamp"] = df.apply(lambda row: datetime.datetime(row["year"],row["month"],row["day"],row["hour"],row["minute"]), axis=1)
  df = concatenate(df, "text", datetime.timedelta(minutes=30))
  df = get_turn(df, "text", datetime.timedelta(minutes=30))
  df.to_csv(args.output, sep=args.sep,index=False)





