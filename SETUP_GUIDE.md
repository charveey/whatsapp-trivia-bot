# Setup Guide

This guide will walk you through setting up the WhatsApp Trivia Bot from scratch.

## Prerequisites

- Python 3.7 or higher
- pip (Python package installer)
- Chrome or Chromium browser
- A WhatsApp account
- Basic command line knowledge

## Step-by-Step Setup

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/whatsapp-trivia-bot.git
cd whatsapp-trivia-bot
```

### 2. Create a Virtual Environment (Recommended)

**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**On Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Find Your WhatsApp Group ID

There are several ways to find your group ID:

#### Method 1: Print All Incoming Messages
Add this temporary code to your bot:

```python
def print_message_info(message):
    print(f"From: {message.get('from')}")
    print(f"Body: {message.get('body')}")
    print("-" * 50)

# In your bot initialization:
bot.creator.client.onMessage(print_message_info)
```

Send a message in your target group and look for the `from` field.

#### Method 2: Use WhatsApp Web Developer Tools
1. Open WhatsApp Web
2. Open Developer Tools (F12)
3. Go to Console
4. Find your group and inspect its ID in the HTML

The group ID format looks like: `123456789-1234567890@g.us`

### 5. Configure the Bot

Edit `trivia_bot.py` and update these variables in the `main()` function:

```python
SESSION_NAME = "trivia_bot"  # Can be any name
GROUP_ID = "YOUR-GROUP-ID@g.us"  # Replace with your actual group ID
CSV_PATH = "questions.csv"
```

### 6. Prepare Your Questions

Create or edit `questions.csv` with your trivia questions:

```csv
question,answers
What is 2+2?,4|four|2+2
Capital of France?,Paris|paris
```

**Tips for writing questions:**
- Use the pipe `|` character to separate alternative answers
- Answers are case-insensitive
- Punctuation is automatically removed
- Keep questions clear and unambiguous

### 7. First Run - QR Code Scan

Run the bot for the first time:

```bash
python trivia_bot.py
```

A QR code will appear in your terminal or a Chrome window will open. Scan this with WhatsApp:

1. Open WhatsApp on your phone
2. Go to Settings → Linked Devices
3. Tap "Link a Device"
4. Scan the QR code

The session will be saved, so you won't need to scan again.

### 8. Test the Bot

Before running a full game, test with a single question:

1. Edit your `questions.csv` to have just one question
2. Run the bot
3. Verify it posts to the correct group
4. Test answering the question
5. Check if the bot recognizes correct answers

### 9. Adjust Timing (Optional)

If questions are too fast or slow, adjust these constants:

```python
QUESTION_DURATION = 15  # Time to answer (seconds)
REP_DELAY = 10         # Delay before showing answer (seconds)
NEXT_DELAY = 5         # Delay before next question (seconds)
```

## Common Issues

### Issue: "Connection failed: DISCONNECTED"

**Solutions:**
- Ensure Chrome/Chromium is installed
- Check your internet connection
- Delete the session folder and re-scan QR code
- Try running with administrator/sudo privileges

### Issue: Bot doesn't detect answers

**Solutions:**
- Verify the `GROUP_ID` is correct
- Ensure you're testing in the right group
- Check that answers match exactly (accounting for normalization)
- Add debug prints to `check_answer()` method

### Issue: QR code doesn't appear

**Solutions:**
- Ensure Chrome is installed and in your PATH
- Try setting the browser path explicitly in WPP_Whatsapp
- Check if port 3000 is available (default for WPP)

### Issue: Messages arrive out of order

This is usually due to network delays. The bot uses timestamps to handle this correctly, but you may want to:
- Increase `QUESTION_DURATION` for slower connections
- Check system time synchronization

## Running in Production

### Using Screen (Linux/macOS)

Keep the bot running after closing terminal:

```bash
screen -S trivia_bot
python trivia_bot.py
# Press Ctrl+A then D to detach
```

Reattach later:
```bash
screen -r trivia_bot
```

### Using PM2 (Cross-platform)

```bash
npm install -g pm2
pm2 start trivia_bot.py --interpreter python3
pm2 save
pm2 startup
```

## Security Considerations

1. **Never commit session files** - They contain your WhatsApp credentials
2. **Use environment variables** for sensitive config
3. **Limit group permissions** - Only allow admins to send messages if possible
4. **Monitor bot activity** - Keep logs of what the bot does
5. **Rate limiting** - Be mindful of WhatsApp's message limits

## Next Steps

- Customize the question format
- Sync results to a Google Sheets
- Add user statistics tracking
- Create a web dashboard for results

## Getting Help

- Check the [README.md](README.md) for general usage
- Open an issue on GitHub
- Review WhatsApp Web API documentation
- Check WPP_Whatsapp documentation
