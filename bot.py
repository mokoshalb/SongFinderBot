import sys
import os
import re
import time
import asyncio
import requests
import platform
import subprocess
import validators
from shazamio import Shazam
from pytube import YouTube
from twickster import API

USERNAME = "songfindercat"
ID = "1546879800123473922"
BASE_URL = "https://nodetent.com/projects/songfindercat/"
GETTER = BASE_URL+"modules/getter.php"
SETTER = BASE_URL+"modules/setter.php"

os_name = platform.system()
tempPath = "temp/"

if os_name == 'Darwin':
    ffmpeg = "ffmpeg"
    print("This is macOS (Mac).")
elif os_name == 'Windows':
    ffmpeg = "C:\\ffmpeg\\bin\\ffmpeg.exe"
    print("This is Windows.")
else:
    ffmpeg = "ffmpeg"
    print("This is a different operating system.")

def main():
    try:
        api = API()
        api.log('Starting Twitter API Engine')
        api.login(name="songfindercat")
        lastfile = open("lastid.txt", "r")
        since_id = int(lastfile.readline())
        lastfile.close()
        while True:
            ordinaryComment =  False
            tweets, since_id = api.getNotifications(since_id)
            for tweet in tweets:
                if "quoted_status_id_str" in tweet and tweet["quoted_status_id_str"] is not None:
                    api.log("This is a quote request.")
                    tweetid = tweet["quoted_status_id_str"]
                elif "in_reply_to_status_id_str" in tweet and tweet["in_reply_to_status_id_str"] is not None:
                    api.log("This is a reply request.")
                    tweetid = tweet["in_reply_to_status_id_str"]
                else:
                    api.log("Assuming it is a self request.")
                    tweetid = tweet["id_str"]
                    ordinaryComment = True
                if f"@{USERNAME}" in str(tweet["full_text"]).lower() and str(tweetid) != ID:
                    match = re.search(r"frame([1-4])", str(tweet["full_text"]).lower())
                    if match:
                        frame_number = int(match.group(1))
                    else:
                        frame_number = 1
                    tid = str(tweet["id_str"])
                    tweetuser = str(tweet["user_data"]["screen_name"])
                    api.log("Replying @"+tweetuser)
                    getter = requests.post(GETTER, data={'tweetid': tweetid, 'hashy':'_hashy_'}).json()
                    if getter["status"] == 1:
                        api.log("Existing, no need to process")
                        api.createTweet("{song} by {artiste}.\n\nDownload & Listen to it here:\n{link}".format(song=getter["title"], artiste=getter["artiste"], link=BASE_URL+tweetid), tid)
                    else:
                        api.log("New, require processing")
                        video = api.getVideo(tweetid, frame_number)
                        if validators.url(video):
                            r = requests.get(video, allow_redirects=True, stream=True)
                            tweetvideo = tempPath+tweetid+".mp4"
                            with open(tweetvideo, "wb") as vid:
                                for chunk in r.iter_content(chunk_size=1024):
                                    if chunk:
                                        vid.write(chunk)
                                        vid.flush()
                            loop = asyncio.get_event_loop()
                            songData = loop.run_until_complete(recognize(tweetvideo))
                            if len(songData["matches"]) > 0 and songData["track"] is not None:
                                songTitle = songData["track"]["title"]
                                songArtist = songData["track"]["subtitle"]
                                songKey = songData["track"]["key"]
                                for section in songData["track"]["sections"]:
                                    if str(section["type"]).lower() == "video" and section["youtubeurl"] is not None:
                                        yt = requests.get(section["youtubeurl"]).json()
                                        youtubeURL = yt["actions"][0]["uri"]
                                        thumbnail = yt["image"]["url"]
                                        videoFile = YouTube(youtubeURL).streams.get_by_itag(18).download(output_path=tempPath, filename=tweetid+"yt")
                                        outputFile = tempPath+songKey+".mp3"
                                        subprocess.run([ffmpeg, '-loglevel', 'quiet', '-hide_banner', '-y', '-i', videoFile, '-vn', '-acodec', 'libmp3lame', '-ar', '44100', '-ac', '2', outputFile])
                                        fh = open(outputFile, "rb")
                                        fh.seek(0)
                                        content = requests.post(url="https://pomf.lain.la/upload.php", files={"files[]":fh})
                                        fh.close()
                                        mp3 = content.json()["files"][0]["url"]
                                        setter = requests.post(SETTER, data={'hashy':'_hashy_', 'tweetid': tweetid, 'title': songTitle, 'thumbnail': thumbnail, 'video': youtubeURL, 'audio': mp3, 'artiste': songArtist, 'shazam': songKey}).text
                                        api.log(setter)
                                        api.createTweet("{song} by {artiste}.\n\nDownload & Listen to it here:\n{link}".format(song=songTitle, artiste=songArtist, link=BASE_URL+tweetid), tid)
                            else:
                                api.createTweet("not sure what that sounds like man :(", tid)
                                api.log("No song found")
                        else:
                            if not ordinaryComment:
                                api.createTweet("not sure what that sounds like man :(", tid)
                                api.log("Not a video tweet")
            lastfile2 = open("lastid.txt", "w")
            lastfile2.write(str(since_id))
            lastfile2.close()
            api.log("Completed a batch.")
            time.sleep(15)
            wipeFolder(tempPath)
    except KeyboardInterrupt:
        api.log("Interrupted by user.")
        wipeFolder(tempPath)
    except Exception as error:
        api.log("Some error occured.")
        api.log(error)
        wipeFolder(tempPath)
        crash = "Error on line {line} at {time}\n{error}\n\n".format(line=sys.exc_info()[-1].tb_lineno, time=str(time.strftime("%H:%M:%S", time.localtime())), error=error)
        with open("error_log.txt","a") as crashLog:
            crashLog.write(crash)

async def recognize(file):
    shazam = Shazam()
    out = await shazam.recognize_song(file)
    return out

def wipeFolder(folder_path):
    for root, dirs, files in os.walk(folder_path, topdown=False):
        for file in files:
            file_path = os.path.join(root, file)
            os.remove(file_path)
        for dir in dirs:
            dir_path = os.path.join(root, dir)
            os.rmdir(dir_path)
    return True

if __name__ == '__main__':
    main()
