import concurrent.futures
import os
import re
import threading
import urllib.parse

import requests

##### ##### ##### ##### #####

# Regular expression to match the URL pattern for attachments
ATTACHMENT_REGEX = re.compile(r"^/attachments/(\d+)/(\d+)/([^/]+)$")

# Regular expression to match the URL pattern for decorations
DECORATIONS_REGEX = re.compile(r"^/(app-icons|avatars|banners|icons)/(\d+)/([^/]+)\.(\w+)$")

# Regular expression to match the URL pattern for emojis
EMOJI_REGEX = re.compile(r"^/(emojis|stickers)/(\d+)\.(\w+)$")

"""
guilds/guild_id/users/user_id/avatars/member_avatar.png
app-assets/710982414301790216/store/sticker_pack_banner_asset_id.png
guilds/guild_id/users/user_id/banners/member_banner.png *	PNG, JPEG, WebP, GIF
app-assets/710982414301790216/store/sticker_pack_banner_asset_id.png	PNG, JPEG, WebP

"""

##### ##### ##### ##### #####

# Create a thread pool executor to download attachments concurrently
executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

# Create a lock to synchronize access to the set of downloading files
download_lock = threading.Lock()

# Create a set to keep track of the files that are currently being downloaded
downloading_files = set()

##### ##### ##### ##### #####

def download(url, path):
  # Acquire the lock
  with download_lock:
    # If the file is already being downloaded
    if path in downloading_files:
      # Return to avoid downloading the same file multiple times
      return

    # Add the file to the set of downloading files
    downloading_files.add(path)

  try:
    # Download the file using the URL
    with requests.get(url, stream=True) as response:
      # Throw exception if the response status code is not 200
      response.raise_for_status()

      # Open a file to write the content
      with open(path, "wb") as file:
        # Write the content to the file in chunks
        for chunk in response.iter_content(chunk_size=8192): 
          # Write the chunk to the file
          file.write(chunk)

      # Print a message indicating that the file has been downloaded
      print(f"Downloaded {url.split('?')[0]}")
  except Exception as e:
    # Print the error message
    print(f"Error downloading {url}: {e}")
  finally:
    # Acquire the lock
    with download_lock:
      # Remove the file from the set of downloading files
      downloading_files.remove(path)

##### ##### ##### ##### #####

def response(flow):
  # Parse the URL of the request
  url = urllib.parse.urlparse(flow.request.url)

  # Check if the URL path matches the pattern for attachments
  if (url.hostname == "cdn.discordapp.com" or url.hostname == "media.discordapp.net") and flow.request.method == "GET" and (match := ATTACHMENT_REGEX.match(url.path)):
    # If the response status code is not 200
    if flow.response.status_code != 200:
      # Return to avoid writing the attachment
      return

    # Check for path traversal in the attachment URL
    if ".." in match.group(1) or ".." in match.group(2) or ".." in match.group(3):
      # Return to avoid writing the attachment with a path traversal in the filename
      return

    # Create the directory for the attachment
    os.makedirs(os.path.join("data", "attachments", match.group(1), match.group(2)), exist_ok=True)

    # If the file for the attachment already exists
    if os.path.exists(os.path.join("data", "attachments", match.group(1), match.group(2), match.group(3))):
      # Return to avoid writing the same attachment again
      return

    # Parse the query parameters of the URL
    query = urllib.parse.parse_qs(url.query)

    # If the query parameters "ex", "is" or "hm" are not in the URL query
    if "ex" not in query or "is" not in query or "hm" not in query:
      # Return to avoid writing the attachment
      return

    # Submit a task to the thread pool executor
    executor.submit(download, f"https://cdn.discordapp.com/attachments/{match.group(1)}/{match.group(2)}/{match.group(3)}?ex={query['ex'][0]}&is={query['is'][0]}&hm={query['hm'][0]}", os.path.join("data", "attachments", match.group(1), match.group(2), match.group(3)))

  # Check if the URL path matches the pattern for emojis
  if (url.hostname == "cdn.discordapp.com" or url.hostname == "media.discordapp.net") and flow.request.method == "GET" and (match := EMOJI_REGEX.match(url.path)):
    # If the response status code is not 200
    if flow.response.status_code != 200:
      # Return to avoid writing the attachment
      return

    # Check for path traversal in the attachment URL
    if ".." in match.group(2) or ".." in match.group(3):
      # Return to avoid writing the attachment with a path traversal in the filename
      return

    # Create the directory for the decoration
    os.makedirs(os.path.join("data", "emojis"), exist_ok=True)

    # If the file for the attachment already exists
    if os.path.exists(os.path.join("data", "emojis", f"{match.group(2)}.{match.group(3)}")):
      # Return to avoid writing the same attachment again
      return

    # Submit a task to the thread pool executor
    executor.submit(download, f"https://cdn.discordapp.com/emojis/{match.group(2)}.{match.group(3)}?size=4096", os.path.join("data", "emojis", f"{match.group(2)}.{match.group(3)}"))

  # Check if the URL path matches the pattern for decorations
  if (url.hostname == "cdn.discordapp.com" or url.hostname == "media.discordapp.net") and flow.request.method == "GET" and (match := DECORATIONS_REGEX.match(url.path)):
    # If the response status code is not 200
    if flow.response.status_code != 200:
      # Return to avoid writing the attachment
      return

    # Check for path traversal in the attachment URL
    if ".." in match.group(1) or ".." in match.group(2) or ".." in match.group(3):
      # Return to avoid writing the attachment with a path traversal in the filename
      return

    # Force the file extension to be png for all decorations
    ext = "png"

    # If the decoration is an animated decoration
    if match.group(3).startswith("a_"):
      # Force the file extension to be gif
      ext = "gif"

    # Create the directory for the decoration
    os.makedirs(os.path.join("data", match.group(1), match.group(2)), exist_ok=True)

    # If the file for the attachment already exists
    if os.path.exists(os.path.join("data", match.group(1), match.group(2), f"{match.group(3)}.{ext}")):
      # Return to avoid writing the same attachment again
      return

    # Submit a task to the thread pool executor
    executor.submit(download, f"https://cdn.discordapp.com/{match.group(1)}/{match.group(2)}/{match.group(3)}.{ext}?size=4096", os.path.join("data", match.group(1), match.group(2), f"{match.group(3)}.{ext}"))
