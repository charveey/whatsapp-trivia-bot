# WhatsApp Trivia Bot

A Python-based trivia game bot for WhatsApp groups that manages timed questions, tracks responses, and maintains a leaderboard.

## Requirements

- Python 3.7+
- [WPP_Whatsapp](https://github.com/3mora2/WPP_Whatsapp) library
- A WhatsApp account for the bot
- Chrome/Chromium browser (for WPP_Whatsapp)

## Installation

1. Clone the repository:

```bash
git clone https://github.com/charveey/whatsapp-trivia-bot.git
cd whatsapp-trivia-bot
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set up your WhatsApp session:
   - Run the bot for the first time
   - Scan the QR code with WhatsApp on your phone
   - The session will be saved for future runs

## Configuration

### Bot Settings

Edit the constants at the top of `trivia_bot.py`:

```python
QUESTION_DURATION = 15  # Seconds to answer each question
REP_DELAY = 10         # Delay before revealing answers
NEXT_DELAY = 5         # Delay before next question
```

### Session and Group

In the `main()` function, configure:

```python
SESSION_NAME = "trivia_bot"  # Your session name
GROUP_ID = "your-group-id@g.us"  # WhatsApp group ID
CSV_PATH = "questions.csv"  # Path to questions file
```

To find your group ID, you can use WhatsApp Web developer tools or print incoming messages.

## Questions Format

Create a `questions.csv` file with the following structure:

```csv
question,answers
What is the capital of France?,Paris|paris
Who painted the Mona Lisa?,Leonardo da Vinci|Da Vinci|Leonardo|davinci
What year did World War II end?,1945
```

- **question**: The trivia question text
- **answers**: Pipe-separated list of acceptable answers (case-insensitive)

## Usage

Run the bot:

```bash
python trivia_bot.py
```

The bot will:

1. Connect to WhatsApp
2. Load questions from CSV
3. Send questions to the configured group
4. Track answers in real-time
5. Display results after each question
6. Generate a final leaderboard

### Game Flow

For each question:

1. **Question sent** → Participants have `QUESTION_DURATION` seconds to answer
2. **STOP** → Question time has ended
3. **REP** → Correct answer revealed (quotes first correct response)
4. **NEXT** → Moving to next question

## Leaderboard

After all questions are completed:

- Leaderboard is printed to console
- Option to save to CSV with columns:
  - Question
  - Winner1-5 (names)
  - Time1-5 (timestamps)
  - ResponseTime1-5 (seconds after question)

## How It Works

### Timestamp Validation

The bot uses WhatsApp message timestamps to ensure fair play:

- Only answers sent **after** the question is posted are valid
- Only answers sent **before** the cutoff time are counted
- Late answers are logged but not scored

### Thread Safety

The bot uses locks to safely handle:

- Concurrent message processing
- State updates during question flow
- Leaderboard data collection

### Answer Normalization

Answers are normalized to allow flexible matching:

- Case-insensitive
- Punctuation removed
- Whitespace trimmed

## Testing

Run the test suite:

```bash
pytest tests/
```

Run with coverage:

```bash
pytest --cov=trivia_bot tests/
```

## Project Structure

```sh
whatsapp-trivia-bot/
├── trivia_bot.py          # Main bot code
├── questions.csv          # Trivia questions
├── leaderboard.csv        # Generated leaderboard
├── requirements.txt       # Python dependencies
├── tests/
│   ├── test_trivia_bot.py # Unit tests
│   └── test_integration.py # Integration tests
├── .gitignore
├── LICENSE
└── README.md
```

## Troubleshooting

### Connection Issues

- Ensure Chrome/Chromium is installed
- Delete the session folder and re-scan QR code
- Check your internet connection

### Messages Not Being Detected

- Verify the `GROUP_ID` is correct
- Check that the bot has permission to read group messages
- Ensure questions are sent before answers

### Timing Issues

- Adjust `QUESTION_DURATION` if too short/long
- Check system time synchronization
- Verify message timestamps are being received

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

## License

MIT License - see LICENSE file for details

## Disclaimer

This bot is for educational and entertainment purposes. Ensure you comply with WhatsApp's Terms of Service when using automation tools.

## Acknowledgments

- [WPP_Whatsapp](https://github.com/3mora2/WPP_Whatsapp) for the WhatsApp API wrapper
- Contributors and testers