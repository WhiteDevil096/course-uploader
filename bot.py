import html
import os
import json
import time
import io
import re
import base64
import requests
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

# ==================== CONFIGURATION ====================
BOT_TOKEN = "8973207677:AAH2RgsyBeBQ9uPqk0tsCZA63fhUzacoTGI"
ADMIN_ID = 1491733638

# Aapka Target Supergroup
CHAT_ID = -1004446069609
GROUP_NAME = "SW COMPLETE BATCH"

BASE_DIR = "All_Batches"
# Direct fixed thumbnail URL (No input prompt)
IMAGE_LINK_INPUT = "https://i.pinimg.com/originals/78/36/99/783699f4ae83a604f9e005e88f883c81.jpg?nii=t"
DEFAULT_FACULTY = "Faculty"
SHOULD_PIN = True

PROGRESS_FILE = "batch_progress.json"
# =======================================================

bot = telebot.TeleBot(BOT_TOKEN)


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_progress(batch_name, class_index):
    data = load_progress()
    data[batch_name] = class_index
    try:
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def format_tg_message_link(group_id, message_id):
    """Supergroup me message ka direct clickable link banata hai."""
    clean_id = str(group_id)
    if clean_id.startswith("-100"):
        clean_id = clean_id[4:]
    elif clean_id.startswith("-"):
        clean_id = clean_id[1:]
    return f"https://t.me/c/{clean_id}/{message_id}"


def extract_real_image_bytes(raw_url: str):
    """Image ko memory buffer me download karta hai"""
    if not raw_url or raw_url.lower() == "none":
        return None

    raw_url = raw_url.strip()

    if raw_url.startswith("data:image/"):
        try:
            header, encoded = raw_url.split(",", 1)
            img_data = base64.b64decode(encoded)
            bio = io.BytesIO(img_data)
            bio.name = "thumb.jpg"
            return bio
        except Exception as e:
            print(f"Base64 error: {e}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        resp = requests.get(raw_url, headers=headers, timeout=15, allow_redirects=True)
        content_type = resp.headers.get("Content-Type", "").lower()

        if "image" in content_type:
            bio = io.BytesIO(resp.content)
            bio.name = "thumb.jpg"
            return bio
    except Exception as e:
        print(f"⚠️ Thumbnail warning: {e}")

    return None


def create_single_batch_topic(group_id, batch_name):
    """Batch folder ke naam par ek single forum topic banata hai."""
    topic_title = batch_name.strip()
    if len(topic_title) > 128:
        topic_title = topic_title[:125] + "..."

    try:
        print(f"\n📁 Naya topic create ho raha hai: '{topic_title}'...")
        topic = bot.create_forum_topic(chat_id=group_id, name=topic_title)
        topic_id = topic.message_thread_id
        print(f"✅ Topic '{topic_title}' ban gaya! (ID: {topic_id})")
        time.sleep(1)
        return topic_id
    except Exception as e:
        print(f"⚠️ Topic create notice: {e} (General chat me post hoga)")
        return None


def parse_classes_from_json(json_path, default_faculty="Faculty"):
    """full_classes.json se classes aur subjects extract karta hai."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    parsed_items = []
    raw_classes = data.get("data", {}).get("classes", [])

    for item in raw_classes:
        if isinstance(item, dict) and "classes" in item and isinstance(item["classes"], list):
            topic_subject = item.get("topicName") or "GENERAL"
            for sub_c in item["classes"]:
                if isinstance(sub_c, dict):
                    title = sub_c.get("title")
                    if not title:
                        continue

                    video_url = sub_c.get("class_link") or ""
                    mp4_url = ""
                    for rec in sub_c.get("mp4Recordings", []):
                        if isinstance(rec, dict) and rec.get("quality") == "720p":
                            mp4_url = rec.get("url") or ""
                            break

                    pdf_list = sub_c.get("classPdf", [])
                    faculty = sub_c.get("teacherName") or default_faculty

                    parsed_items.append({
                        "subject": topic_subject,
                        "title": title,
                        "video_url": video_url,
                        "mp4_url": mp4_url,
                        "pdf_list": pdf_list,
                        "faculty": faculty
                    })

        elif isinstance(item, dict):
            topic_subject = item.get("topic", {}).get("topicName") or "GENERAL"
            title = item.get("title")
            if not title:
                continue

            video_url = item.get("class_link") or ""
            mp4_url = ""
            for rec in item.get("mp4Recordings", []):
                if isinstance(rec, dict) and rec.get("quality") == "720p":
                    mp4_url = rec.get("url") or ""
                    break

            pdf_list = item.get("classPdf", [])
            faculty = item.get("teacherName") or default_faculty

            parsed_items.append({
                "subject": topic_subject,
                "title": title,
                "video_url": video_url,
                "mp4_url": mp4_url,
                "pdf_list": pdf_list,
                "faculty": faculty
            })

    return parsed_items


def process_bulk_batches():
    print("🤖 Telegram Group Topic Uploader चालू ho gaya hai!\n")
    print(f"🎯 Target Group : {GROUP_NAME} (ID: {CHAT_ID})")

    # Dynamic folder detection taaki path issue na aaye
    batches_path = None
    search_dirs = [
        os.path.dirname(os.path.abspath(__file__)),
        os.getcwd(),
        os.path.join(os.getcwd(), ".."),
    ]

    for s_dir in search_dirs:
        candidate = os.path.join(s_dir, BASE_DIR)
        if os.path.exists(candidate) and os.path.isdir(candidate):
            batches_path = candidate
            break

    if not batches_path:
        for root, dirs, files in os.walk(os.getcwd()):
            if BASE_DIR in dirs:
                batches_path = os.path.join(root, BASE_DIR)
                break

    if not batches_path or not os.path.exists(batches_path):
        print(f"❌ Error: Folder '{BASE_DIR}' nahi mila!")
        print(f"📂 Current Directory Content: {os.listdir(os.getcwd())}")
        return

    print(f"✅ 'All_Batches' folder mil gaya: {batches_path}")

    print("🖼️ Thumbnail analyze kiya ja raha hai...")
    thumbnail_bio = extract_real_image_bytes(IMAGE_LINK_INPUT)
    thumb_bytes = thumbnail_bio.getvalue() if thumbnail_bio else None
    if thumb_bytes:
        print("✅ Thumbnail ready.")
    else:
        print("⚠️ Thumbnail fetch nahi ho saka, direct text messages send honge.")

    batch_folders = sorted([
        f for f in os.listdir(batches_path)
        if os.path.isdir(os.path.join(batches_path, f))
    ])

    total_batch_count = len(batch_folders)
    print(f"\n📦 '{BASE_DIR}' folder me kul {total_batch_count} batches mile hain.\n")

    progress_data = load_progress()

    for b_idx, folder_name in enumerate(batch_folders, 1):
        batch_folder_full_path = os.path.join(batches_path, folder_name)
        json_path = os.path.join(batch_folder_full_path, "full_classes.json")

        if not os.path.exists(json_path):
            print(f"⚠️ [{b_idx}/{total_batch_count}] '{folder_name}' me full_classes.json nahi mila, skipping.")
            continue

        batch_name = folder_name
        print("=" * 60)
        print(f"📂 [{b_idx}/{total_batch_count}] Batch Name: {batch_name}")

        items = parse_classes_from_json(json_path, DEFAULT_FACULTY)
        total_classes = len(items)

        if total_classes == 0:
            print("❌ Is batch me koi valid classes nahi mili!")
            continue

        topic_id = create_single_batch_topic(CHAT_ID, batch_name)

        start_index = progress_data.get(batch_name, 0)
        if start_index >= total_classes:
            print(f"✅ Batch '{batch_name}' pehle hi complete upload ho chuka hai ({start_index}/{total_classes}).")
            continue

        if start_index > 0:
            print(f"🔄 Resuming from index {start_index + 1}...")
            print(f"📊 Remaining: {total_classes - start_index}/{total_classes}\n")
        else:
            print(f"📊 Total {total_classes} classes mili hain. Posting start...\n")

        # Admin Progress Alert
        progress_msg = None
        try:
            progress_msg = bot.send_message(
                ADMIN_ID,
                (
                    f"🚀 <b>Batch Upload Started!</b>\n\n"
                    f"👥 <b>Group:</b> {html.escape(GROUP_NAME)}\n"
                    f"📌 <b>Batch:</b> {html.escape(batch_name)}\n"
                    f"⏳ <b>Progress:</b> {start_index}/{total_classes}"
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass

        current_subject = None
        posted_count = start_index
        subject_index_map = {}

        for idx in range(start_index, total_classes):
            item = items[idx]
            title = item["title"]
            subject = item["subject"].upper()
            video_url = item["video_url"]
            mp4_url = item["mp4_url"]
            pdf_list = item["pdf_list"]
            faculty_name = item["faculty"]

            is_new_subject = (subject != current_subject)

            while True:
                try:
                    if SHOULD_PIN and is_new_subject:
                        current_subject = subject
                        print(f"\n🔔 Naya vishay: {subject}. Topic me pin message bheja ja raha hai...")
                        pin_text = f"📌 <b>{html.escape(subject)} CLASSES STARTED</b>\n<i>Batch: {html.escape(batch_name)}</i>"
                        pin_msg = bot.send_message(
                            chat_id=CHAT_ID,
                            text=pin_text,
                            parse_mode="HTML",
                            message_thread_id=topic_id,
                        )
                        bot.pin_chat_message(
                            chat_id=CHAT_ID,
                            message_id=pin_msg.message_id,
                            disable_notification=True,
                        )
                        time.sleep(2)
                    elif is_new_subject:
                        current_subject = subject

                    caption = (
                        f"<b>📖 [{idx+1:03d}] {html.escape(title)}</b>\n"
                        f"<b>📌 Chapter:</b> {html.escape(subject)}\n"
                        f"<b>👨‍🏫 Faculty:</b> {html.escape(faculty_name)}\n"
                        f"<b>🏷 Batch:</b> {html.escape(batch_name)}\n"
                        f"<code>━━━━━━━━━━━━━━━━━━━━</code>\n"
                        f"<i>HELP BY WHITEDEVIL</i>"
                    )

                    markup = InlineKeyboardMarkup()
                    btn_row = []
                    if video_url:
                        btn_row.append(InlineKeyboardButton("▶️ STREAM (M3U8)", url=video_url))
                    if mp4_url:
                        btn_row.append(InlineKeyboardButton("📥 DOWNLOAD (720P)", url=mp4_url))
                    if btn_row:
                        markup.row(*btn_row)

                    sent_msg = None
                    if thumb_bytes:
                        try:
                            stream = io.BytesIO(thumb_bytes)
                            stream.name = "thumb.jpg"
                            sent_msg = bot.send_photo(
                                chat_id=CHAT_ID,
                                photo=stream,
                                caption=caption,
                                parse_mode="HTML",
                                reply_markup=markup if btn_row else None,
                                message_thread_id=topic_id,
                            )
                        except Exception:
                            sent_msg = bot.send_message(
                                chat_id=CHAT_ID,
                                text=caption,
                                parse_mode="HTML",
                                reply_markup=markup if btn_row else None,
                                message_thread_id=topic_id,
                            )
                    else:
                        sent_msg = bot.send_message(
                            chat_id=CHAT_ID,
                            text=caption,
                            parse_mode="HTML",
                            reply_markup=markup if btn_row else None,
                            message_thread_id=topic_id,
                        )

                    # Attached PDF Notes
                    if pdf_list:
                        pdf_lines = []
                        for p in pdf_list:
                            if isinstance(p, dict) and p.get("url"):
                                p_name = p.get("name") or "Lecture PDF"
                                pdf_lines.append(f"📄 <a href=\"{p['url']}\">{html.escape(p_name)}</a>")
                        if pdf_lines:
                            pdf_msg = "<b>📚 Attached Notes:</b>\n" + "\n".join(pdf_lines)
                            bot.send_message(
                                chat_id=CHAT_ID,
                                text=pdf_msg,
                                parse_mode="HTML",
                                message_thread_id=topic_id,
                                disable_web_page_preview=True
                            )

                    if is_new_subject and sent_msg:
                        post_link = format_tg_message_link(CHAT_ID, sent_msg.message_id)
                        subject_index_map[subject] = post_link

                    posted_count += 1
                    save_progress(batch_name, idx + 1)

                    # Admin DM Update
                    if progress_msg and (posted_count % 10 == 0 or posted_count == total_classes):
                        try:
                            bot.edit_message_text(
                                chat_id=ADMIN_ID,
                                message_id=progress_msg.message_id,
                                text=(
                                    f"🚀 <b>Batch Uploading...</b>\n\n"
                                    f"👥 <b>Group:</b> {html.escape(GROUP_NAME)}\n"
                                    f"📌 <b>Batch:</b> {html.escape(batch_name)}\n"
                                    f"✅ <b>Posted:</b> {posted_count}/{total_classes}\n"
                                    f"⏳ <b>Remaining:</b> {total_classes - posted_count}\n\n"
                                    f"<i>Topic: {subject} | Class: {html.escape(title)}</i>"
                                ),
                                parse_mode="HTML",
                            )
                        except Exception:
                            pass

                    print(f"\r⚡ Uploaded: {idx + 1}/{total_classes} ({((idx+1)/total_classes)*100:.1f}%) | {title[:30]}...", end="", flush=True)
                    time.sleep(2.5)
                    break

                except telebot.apihelper.ApiTelegramException as e:
                    if e.error_code == 429:
                        wait_t = int(e.result_json.get("parameters", {}).get("retry_after", 15))
                        print(f"\n⏳ Rate Limit hit! Waiting {wait_t} seconds...")
                        time.sleep(wait_t + 1)
                    else:
                        print(f"\n⚠️ Telegram Error: {e}. Retrying in 10s...")
                        time.sleep(10)
                except Exception as e:
                    print(f"\n⚠️ Network Error: {e}. Retrying in 10s...")
                    time.sleep(10)

        # Batch Index Post
        if subject_index_map:
            print("\n📑 Batch Index generate ho raha hai...")
            index_text = f"📚 <b>BATCH INDEX - {html.escape(batch_name)}</b>\n\n"
            index_text += "TOPIC LINKS:\n\n"

            for s_name, link in subject_index_map.items():
                index_text += f'🔹 <a href="{link}">{html.escape(s_name)}</a>\n'

            index_text += "\n<code>━━━━━━━━━━━━━━━━━━━━</code>\n<i>HELP BY WHITEDEVIL</i>"

            try:
                bot.send_message(
                    chat_id=CHAT_ID,
                    text=index_text,
                    parse_mode="HTML",
                    message_thread_id=topic_id,
                    disable_web_page_preview=True,
                )
                print("✅ Index message successfully group me post ho gaya!")
                time.sleep(1)
            except Exception as e:
                print(f"⚠️ Index post notice: {e}")

        # Final Completion Ping
        try:
            bot.send_message(
                chat_id=CHAT_ID,
                text=f"<b>COMPLETED💀</b>\n<i>Batch: {html.escape(batch_name)}</i>",
                parse_mode="HTML",
                message_thread_id=topic_id,
            )
            print("✅ 'COMPLETED💀' send ho gaya!")
        except Exception:
            pass

        print(f"\n🎉 Batch '{batch_name}' poora upload ho gaya!\n")

    print("\n" + "=" * 50)
    print("🏆 Sabhi batches successfully upload ho chuke hain!")


if __name__ == "__main__":
    process_bulk_batches()
