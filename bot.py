import os
import re
import json
import asyncio
import urllib.request
import urllib.parse

# Environment variables se credentials lena (GitHub Actions Secrets)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID_RAW = os.environ.get("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID_RAW:
    print("❌ Error: BOT_TOKEN ya CHAT_ID environment variables me set nahi hain!", flush=True)
    exit(1)

CHAT_ID = int(CHAT_ID_RAW)

# Default Thumbnail URL
DEFAULT_THUMBNAIL = "https://skipsuniversity.edu.in/wp-content/uploads/2023/09/btech.png"
THUMBNAIL_URL = os.environ.get("THUMBNAIL_URL", "").strip() or DEFAULT_THUMBNAIL

FOLDER_PATH = "./txt_files"
STATE_FILE = "progress_state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4)
    except Exception as e:
        print(f"⚠️ Progress save karne me error: {e}", flush=True)

def make_telegram_request(endpoint: str, payload: dict):
    """
    Direct Telegram HTTP Bot API request.
    Isme Pyrogram ka Peer ID issue bilkul nahi hota.
    """
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{endpoint}"
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers)

    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode())
            return True, res_data
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        try:
            error_json = json.loads(error_body)
            retry_after = error_json.get("parameters", {}).get("retry_after")
            return False, {"error": error_json.get("description", str(e)), "retry_after": retry_after}
        except Exception:
            return False, {"error": str(e), "retry_after": None}
    except Exception as e:
        return False, {"error": str(e), "retry_after": None}

def create_telegram_topic(title: str):
    success, res = make_telegram_request("createForumTopic", {"chat_id": CHAT_ID, "name": title})
    if success and res.get("ok"):
        return res["result"]["message_thread_id"], None
    err = res.get("error", "Unknown error") if isinstance(res, dict) else str(res)
    return None, err

def send_telegram_photo(caption: str, photo_url: str, topic_id: int, reply_markup: dict):
    payload = {
        "chat_id": CHAT_ID,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "Markdown",
        "message_thread_id": topic_id,
        "reply_markup": reply_markup
    }
    return make_telegram_request("sendPhoto", payload)

def send_telegram_message(text: str, topic_id: int, reply_markup: dict):
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "message_thread_id": topic_id,
        "reply_markup": reply_markup,
        "disable_web_page_preview": True
    }
    return make_telegram_request("sendMessage", payload)

def parse_txt_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = content.split("----------------------------")
    items = []

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        title_match = re.search(r"Title:\s*(.+)", block, re.IGNORECASE)
        link_match = re.search(r"(?:Video|Link|URL):\s*(https?://\S+)", block, re.IGNORECASE)

        if title_match and link_match:
            title = title_match.group(1).strip()
            link = link_match.group(1).strip()
            items.append({"title": title, "link": link})
        elif link_match:
            link = link_match.group(1).strip()
            items.append({"title": "Untitled Lecture", "link": link})

    return items

def get_button_text(url: str) -> str:
    if ".bin" in url.lower():
        return "Watch"
    return "Open"

async def main():
    if not os.path.exists(FOLDER_PATH):
        print(f"❌ Error: Folder '{FOLDER_PATH}' nahi mila!", flush=True)
        return

    all_files = [f for f in os.listdir(FOLDER_PATH) if f.lower().endswith(".txt")]
    all_files.sort()

    if not all_files:
        print(f"❌ '{FOLDER_PATH}' me koi bhi .txt file nahi mili.", flush=True)
        return

    total_files = len(all_files)
    state = load_state()

    thumb_url = THUMBNAIL_URL
    state["thumbnail_url"] = thumb_url
    save_state(state)

    print(f"📂 Total {total_files} txt files mili hain.", flush=True)
    print(f"🖼️ Using Thumbnail: {thumb_url}\n", flush=True)

    for file_index, filename in enumerate(all_files, start=1):
        topic_name = os.path.splitext(filename)[0]
        file_path = os.path.join(FOLDER_PATH, filename)

        file_state = state.get("files", {}).get(filename, {})
        if file_state.get("completed", False):
            print(f"⏩ [File {file_index}/{total_files}] '{filename}' already uploaded. Skipping...", flush=True)
            continue

        print("—" * 60, flush=True)
        overall_pct = ((file_index - 1) / total_files) * 100
        print(f"📊 Progress: {file_index - 1}/{total_files} Files Done ({overall_pct:.1f}%) | Remaining: {total_files - (file_index - 1)}", flush=True)
        print(f"📂 Current File: {filename} -> Topic: '{topic_name}'", flush=True)
        print("—" * 60, flush=True)

        # Topic Create ya Resume
        topic_id = file_state.get("topic_id")
        if not topic_id:
            topic_id, err = create_telegram_topic(topic_name)
            if not topic_id:
                print(f"❌ Topic create nahi hua: {err}", flush=True)
                continue
            print(f"✅ Topic Created: '{topic_name}' (ID: {topic_id})", flush=True)

            if "files" not in state:
                state["files"] = {}
            state["files"][filename] = {
                "topic_id": topic_id,
                "last_uploaded_idx": 0,
                "completed": False
            }
            save_state(state)
        else:
            print(f"🔄 Existing Topic ID mila: {topic_id}", flush=True)

        items = parse_txt_file(file_path)
        total_items = len(items)
        last_uploaded = state.get("files", {}).get(filename, {}).get("last_uploaded_idx", 0)

        # Messages bhejna
        for idx in range(last_uploaded, total_items):
            item = items[idx]
            lecture_num = idx + 1
            item_pct = (lecture_num / total_items) * 100

            btn_name = get_button_text(item["link"])
            markup = {
                "inline_keyboard": [
                    [{"text": f"{btn_name} 🔗", "url": item["link"]}]
                ]
            }

            caption_text = (
                f"📌 *Lecture {lecture_num}:* {item['title']}\n"
                f"📁 *Topic:* {topic_name}"
            )

            while True:
                success, resp = send_telegram_photo(caption_text, thumb_url, topic_id, markup)
                if success:
                    state["files"][filename]["last_uploaded_idx"] = lecture_num
                    save_state(state)
                    print(f"  └─> [{lecture_num}/{total_items}] ({item_pct:.1f}%) Sent: {item['title'][:35]}...", flush=True)
                    await asyncio.sleep(1.5)
                    break

                retry_after = resp.get("retry_after")
                if retry_after:
                    print(f"  ⚠️ FloodWait mila: {retry_after}s wait kar rahe hain...", flush=True)
                    await asyncio.sleep(retry_after)
                    continue

                # Photo fail hone par text bhejna
                print(f"  ⚠️ Photo issue ({resp.get('error')}), fallback to text...", flush=True)
                txt_success, txt_resp = send_telegram_message(caption_text, topic_id, markup)
                if txt_success:
                    state["files"][filename]["last_uploaded_idx"] = lecture_num
                    save_state(state)
                    print(f"  └─> [{lecture_num}/{total_items}] ({item_pct:.1f}%) Sent (Text): {item['title'][:35]}...", flush=True)
                    await asyncio.sleep(1.5)
                    break
                else:
                    print(f"  ❌ Send failed: {txt_resp.get('error')}", flush=True)
                    await asyncio.sleep(2)
                    break

        state["files"][filename]["completed"] = True
        save_state(state)
        print(f"✅ Topic '{topic_name}' Done!\n", flush=True)
        await asyncio.sleep(2)

    print("🎉 Sabhi files successfully upload ho chuki hain!", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
