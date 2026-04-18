# AutoX
# Chief of Staff

Chief of Staff is my personal AI desktop assistant for Windows.  
It listens to simple natural language commands and turns them into real actions like opening websites, organizing files, managing email, and handling basic system tasks.

I built this because I wanted one place that could help me move faster without jumping between apps, folders, and browser tabs all the time.

## What it can do

- Open websites quickly
- Search the web
- Organize Downloads
- Find duplicate files
- Find old or large files
- Collect files by type like PDFs or images
- Send emails through Gmail
- Search inbox, sent mail, and spam
- Take screenshots
- Lock the screen
- Mute or change volume
- Close apps

## How it works

You type a command in plain English, and the app figures out what you mean.

For example:

- `open claude.ai`
- `organize my downloads`
- `find duplicate files`
- `send email to boss subject meeting body see you at 10`
- `take a screenshot`
- `mute volume`
- `close chrome`

The app then routes the command to the right action and handles it for you.

## Why I made it

I wanted something that feels more like a real assistant than just another script or button-based tool.

Instead of making me do repetitive desktop tasks manually, Chief of Staff helps me do them faster with simple commands.

## Tech stack

- Python
- CustomTkinter
- Google Gemini API
- Chrome automation
- Windows system automation
- Pillow
- send2trash

## Features in detail

### Web commands
Open websites, search the internet, and jump to common services like Gmail, Claude, ChatGPT, YouTube, Amazon, and Flipkart.

### File tools
Clean up Downloads, remove duplicates, search by keyword, find old files, and sort files by type.

### Email and system control
Compose emails, open inbox or sent mail, scan spam, take screenshots, mute sound, adjust volume, lock the PC, or put it to sleep.

## Example commands

```text
open youtube
search best headphones
organize my downloads
find files older than 6 months
find largest files
send email to rahul subject meeting body see you at 10
open inbox
scan spam
take a screenshot
close discord
```

## Setup

```bash
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name
pip install -r requirements.txt
```

Set your Gemini API key as an environment variable:

```bash
set GEMINI_API_KEY=your_key_here
```

Then run the app:

```bash
python main.py
```

## Requirements

- Windows
- Google Chrome
- Python 3.10 or above
- Gemini API key

## Future plans

- Better command understanding
- Safer confirmation for sensitive actions
- More file tools
- More email features
- A cleaner and more polished interface
- Possible support for more platforms later

## Final note

This started as a hackathon project, but I’m treating it like something I actually want to grow into a real productivity tool.
