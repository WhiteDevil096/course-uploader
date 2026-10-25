import os
import re
import json
import asyncio
import urllib.request
import urllib.parse
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait

# GitHub Actions Secrets / Environment variables
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = int(os.environ["CHAT_ID"])

# Fixed Thumbnail URL
DEFAULT_THUMBNAIL = "https://skipsuniversity.edu.in/wp-content/uploads/2023/09/btech.png"
THUMBNAIL_URL = os.environ.get("THUMBNAIL_URL", "").strip() or DEFAULT_THUMBNAIL

FOLDER_PATH = "./txt_files"
STATE_FILE = "progress_state.json"

app = Client("github_public_uploader", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

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
        print(f"⚠️ Progress save karne me error: {e}")

def create_telegram_topic(bot_token: str, chat_id: int, title: str):
    url = f"https://api.telegram.org/bot{bot_token}/createForumTopic"
    payload = json.dumps({"chat_id": chat_id, "name": title}).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    req = urllib.request.Request(url, data=payload, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode())
            if res_data.get("ok"):
                return res_data["result"]["message_thread_id"], None
            return None, res_data.get("description", "Unknown error")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        try:
            error_json = json.loads(error_body)
            return None, error_json.get("description", str(e))
        except Exception:
            return None, str(e)
    except Exception as e:
        return None, str(e)

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
    async with app:
        if not os.path.exists(FOLDER_PATH):
            print(f"❌ Error: Folder '{FOLDER_PATH}' nahi mila!")
            return

        all_files = [f for f in os.listdir(FOLDER_PATH) if f.lower().endswith(".txt")]
        all_files.sort()

        if not all_files:
            print(f"❌ '{FOLDER_PATH}' me koi bhi .txt file nahi mili.")
            return

        total_files = len(all_files)
        state = load_state()

        thumb_url = THUMBNAIL_URL
        state["thumbnail_url"] = thumb_url
        save_state(state)

        print(f"📂 Total {total_files} txt files mili hain.")
        print(f"🖼️ Using Thumbnail: {thumb_url}\n")

        for file_index, filename in enumerate(all_files, start=1):
            topic_name = os.path.splitext(filename)[0]
            file_path = os.path.join(FOLDER_PATH, filename)

            file_state = state.get("files", {}).get(filename, {})
            if file_state.get("completed", False):
                print(f"⏩ [File {file_index}/{total_files}] '{filename}' already uploaded. Skipping...")
                continue

            print("—" * 60)
            overall_pct = ((file_index - 1) / total_files) * 100
            print(f"📊 Progress: {file_index - 1}/{total_files} Files Done ({overall_pct:.1f}%) | Remaining: {total_files - (file_index - 1)}")
            print(f"📂 Current File: {filename} -> Topic: '{topic_name}'")
            print("—" * 60)

            # Topic handle karna
            topic_id = file_state.get("topic_id")
            if not topic_id:
                topic_id, err = create_telegram_topic(BOT_TOKEN, CHAT_ID, topic_name)
                if not topic_id:
                    print(f"❌ Topic create nahi hua: {err}")
                    continue
                print(f"✅ Topic Created: '{topic_name}' (ID: {topic_id})")

                if "files" not in state:
                    state["files"] = {}
                state["files"][filename] = {
                    "topic_id": topic_id,
                    "last_uploaded_idx": 0,
                    "completed": False
                }
                save_state(state)
            else:
                print(f"🔄 Existing Topic ID mila: {topic_id}")

            items = parse_txt_file(file_path)
            total_items = len(items)
            last_uploaded = state.get("files", {}).get(filename, {}).get("last_uploaded_idx", 0)

            for idx in range(last_uploaded, total_items):
                item = items[idx]
                lecture_num = idx + 1
                item_pct = (lecture_num / total_items) * 100

                btn_name = get_button_text(item["link"])
                markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton(text=f"{btn_name} 🔗", url=item["link"])]
                ])

                caption_text = (
                    f"📌 **Lecture {lecture_num}:** {item['title']}\n"
                    f"📁 **Topic:** {topic_name}"
                )

                while True:
                    try:
                        await app.send_photo(
                            chat_id=CHAT_ID,
                            photo=thumb_url,
                            caption=caption_text,
                            reply_markup=markup,
                            message_thread_id=topic_id
                        )
                        state["files"][filename]["last_uploaded_idx"] = lecture_num
                        save_state(state)
                        print(f"  └─> [{lecture_num}/{total_items}] ({item_pct:.1f}%) Sent: {item['title'][:35]}...")
                        await asyncio.sleep(1.5)
                        break
                    except FloodWait as fw:
                        print(f"  ⚠️ FloodWait mila: {fw.value}s wait kar rahe hain...")
                        await asyncio.sleep(fw.value)
                    except Exception as e:
                        print(f"  ⚠️ Photo issue ({e}), sending text...")
                        try:
                            await app.send_message(
                                chat_id=CHAT_ID,
                                text=caption_text,
                                reply_markup=markup,
                                message_thread_id=topic_id,
                                disable_web_page_preview=True
                            )
                            state["files"][filename]["last_uploaded_idx"] = lecture_num
                            save_state(state)
                        except Exception as send_err:
                            print(f"  ❌ Message send error: {send_err}")
                        await asyncio.sleep(1.5)
                        break

            state["files"][filename]["completed"] = True
            save_state(state)
            print(f"✅ Topic '{topic_name}' Done!\n")
            await asyncio.sleep(2)

        print("🎉 Sabhi files successfully upload ho chuki hain!")

if __name__ == "__main__":
    app.run(main())
