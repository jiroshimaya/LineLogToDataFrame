import re
import os
import pandas as pd
import argparse

# 日付行で分割
def get_date_content(text):
  # 日付行（YYYY/MM/DD(W)）で囲まれた領域をその直前の日付行とセットで取得する正規表現
  # contentが多くの場合、複数行に渡るので, DOTALLで改行を含む行を検出
  re_date = re.compile(r"\n((\d{4})/(\d{2})/(\d{2})\(([月火水木金土日])\))(\n\d{2}:\d{2}\t.+?)(?=\n\d{4}/\d{2}/\d{2}\([月火水木金土日]\)\n\d{2}:\d{2}\t)", re.DOTALL)
  # 最初と最後の要素をfindallできるように日付業を末尾で足す
  text = "\n{}\n1900/01/01(月)\n00:00\t".format(text)
  # 正規表現にマッチする要素を抽出
  contents = re_date.findall(text)
  logs = []
  for datestr, year, month, day, weekday, content in contents:
    # 各マッチ要素を辞書に変換
    obj = {
      "datestr": datestr,
      "year": year,
      "month": month,
      "day": day,
      "weekday": weekday,
      "content": content
    }
    logs.append(obj)

  return logs

# 時刻で分割
def get_time_content(text):
  # 時刻（hh:mm）で囲まれた領域をその直前の時刻とセットで取得する正規表現
  # contentが複数行に渡る可能性を考慮し, DOTALLで改行を含む行を検出
  re_time = re.compile(r"(?<=\n)((\d{2}):(\d{2}))\t(.+?)(?=\n\d{2}:\d{2}\t)", re.DOTALL) 
  # 最初と最後の要素をfindallできるように時刻から始まる行を足す
  text = "\n{}\n00:00\t".format(text)
  # 正規表現にマッチする要素を抽出
  contents = re_time.findall(text)
  logs = []
  for timestr, hour, minute, content in contents:
    # 各マッチ要素を辞書に変換
    obj = {
      "timestr": timestr,
      "hour": hour,
      "minute": minute,
      "content": content
    }
    logs.append(obj)

  return logs

# 時刻に紐づくcontentから名前と投稿文字列を取得
def get_name_and_post(text):
  post = text.split("\t")
  
  # postは基本的に要素数が2以上だが、nameに相当する要素がなく、要素数が1のケースがある。
  # 要素数が1のケースは原則システムメッセージであるため、
  # 要素数が1の場合はシステムメッセージとみなし、投稿者名を"system"とする
  if len(post) == 1:
    name = "system"
    content = post[0] #2つめの要素をcontentとして取得
  else: #要素数が2より大きいとき、1つめの要素を投稿者名として取得
    name = post[0] if post[0] else "system"
    content = "\t".join(post[1:]) # 3つ目以降をcontentとして取得
  
  return {
    "name": name,
    "content": content
  }

# 投稿の種類を決定し、必要な情報と合わせて返す
def parse_post(content):
  # urlを抽出する正規表現
  re_url = re.compile(r"(https?|ftp)(:\/\/[-_\.!~*\'()a-zA-Z0-9;\/?:\@&=\+$,%#]+)")

  # 汎用的なパラメータ用のキーを追加
  log = {
    "param0_key": "",
    "param0_val": "",
    "param1_key": "",
    "param1_val": ""
  }

  # send_typeを判定
  # ファイル、スタンプ、写真、動画、ボイスメッセージ、連絡先、プレゼントの判定
  if re.fullmatch(r"\[(?:ファイル|スタンプ|写真|動画|ボイスメッセージ|連絡先|プレゼント)\]", content):
    log["send_type"] = content[1:-1]
  # アルバムの判定
  elif content == "[アルバム] (null)":
    log["send_type"] = "アルバム"
  # 位置情報の判定
  elif content.startswith("[位置情報]"):
    log["send_type"] = "位置情報"
  # ノートの判定
  elif content.startswith("[ノート] "):
    log["send_type"] = "ノート"
  # 通話開始の判定
  elif re.fullmatch(r"☎ 通話時間 \d+:\d+",content):
    phone_time = content.split(" ")[-1].split(":")
    phone_sec = int(phone_time[0]) * 60 + int(phone_time[1])
    log.update({
      "send_type":"phone_start",
      "param0_key": "phone_sec",
      "param0_val": phone_sec
    })
  # 通話終了の判定
  elif content == "☎ 通話をキャンセルしました":
    log.update({
      "send_type":"phone_cancel"
    })
  # 上記のいずれでもないとき、テキスト投稿とみなす
  else:
    # urlを取得
    urls = re_url.findall(content)
    log.update({
      "send_type":"text",
      "param0_key": "url_num", # 投稿に含まれるurlの数
      "param0_val": len(urls), 
      "param1_key": "url_remove_length", # urlをまとめて1文字とみなしたときの投稿の文字数
      "param1_val": len(content) + len(urls) - sum([len(url) for url in urls])# urlを1文字としてカウント
    })
  # 投稿の長さを取得
  log["length"] = len(content)
  return log

# lineのトーク履歴から各投稿の情報を抽出する
def parse_linelog(textdata):
  logs = []
  # 日付行の間の文字列を取得
  for date_content_info in get_date_content(textdata):
    # 文字列と日付情報に分ける
    date_content = date_content_info.pop("content")
    date_info = {
      "year": date_content_info.pop("year"),
      "month": date_content_info.pop("month"),
      "day": date_content_info.pop("day"),
      "weekday": date_content_info.pop("weekday"),
      "datestr": date_content_info.pop("datestr")
    }
    # 日付の間の文字列のうち時刻の間の文字列を取得
    for time_content_info in get_time_content(date_content):
      # 文字列と時刻情報を分ける
      time_content = time_content_info.pop("content")
      time_info = {
        "hour": time_content_info.pop("hour"),
        "minute": time_content_info.pop("minute"),
        "timestr": time_content_info.pop("timestr")
      }
      # 投稿者名と投稿内容を取得
      name_and_post_info = get_name_and_post(time_content)
      name = name_and_post_info.pop("name")
      post = name_and_post_info.pop("content")
      # 投稿のsend_typeの情報などを取得
      postinfo = parse_post(post)
      # 投稿から改行、タブを取り除いた文字列を取得
      post_no_tab_and_br = "<br>".join(post.replace("\t", "<tab>").splitlines())

      # 日付、時刻、投稿内容の情報をすべて含んだ辞書を作成
      log = {}
      log.update(date_info)
      log.update(time_info)
      log.update({
        "name": name,
        "content": post,
        "send_type": postinfo.pop("send_type"),
        "length": postinfo.pop("length"),
        "content_no_tab_and_br": post_no_tab_and_br
      })
      logs.append(log)
  return logs

def getArgs():
  parser = argparse.ArgumentParser(description="lineのトーク履歴から各投稿の情報を抽出する")
  parser.add_argument("-i", "--input", help="lineのトーク履歴ファイル", required=True)
  parser.add_argument("-o", "--output", help="抽出した投稿の情報を保存するファイル", required=True)
  args = parser.parse_args()
  return args

if __name__=="__main__":
  args = getArgs()
  PATH = args.input
  textdata = ""
  with open(PATH, "r") as f:
    textdata = f.read()

  # dfに情報として含める列名を定義
  header = ["datestr","timestr","name","content_no_tab_and_br","send_type","year","month","day","weekday","hour","minute","length","param0_key","param0_val","param1_key","param1_val"]
  # lineのトーク履歴のパース結果を取得
  logs = parse_linelog(textdata)
  # dfに変換
  df = pd.DataFrame({k: [v.get(k,"") for v in logs] for k in header})
  # 改行、タブなしの投稿文字列をcontentとして取得
  df = df.rename(columns = {"content_no_tab_and_br":"content"})
  # 保存
  df.to_csv(args.output, sep="\t", index=False, header=True)