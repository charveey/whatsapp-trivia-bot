"""
WhatsApp Trivia Bot

A bot that runs timed trivia games in WhatsApp groups, tracks correct answers,
and generates leaderboards. Uses WhatsApp Web API via WPP_Whatsapp library.

Author: Kevin AMLAMAN
License: MIT
"""

import asyncio
import csv
import os
import re
import time
import traceback
from threading import Lock

from dotenv import load_dotenv
from WPP_Whatsapp import Create

# ============================================================================
# CONFIGURATION CONSTANTS
# ============================================================================

load_dotenv()

QUESTION_DURATION = 15  # Seconds participants have to answer
REP_DELAY = 10  # Seconds to wait before revealing answers
NEXT_DELAY = 5  # Seconds to wait before next question
LEADERBOARD_CSV = "leaderboard.csv"  # Output file for results
SESSION_NAME = "trivia_bot"
GROUP_ID = os.getenv("PROD_ID")
CSV_PATH = "questions.csv"


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def load_questions_from_csv(path):
    """
    Load trivia questions from a CSV file.

    Expected CSV format:
        question,answers
        "What is 2+2?","4|four"
        "Capital of France?","Paris|paris"

    Args:
        path (str): Path to the CSV file

    Returns:
        list[dict]: List of question dictionaries with format:
            {
                'question': str,
                'answers': set of str (lowercase, stripped)
            }
    """
    questions = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            question = row["question"].strip()
            # Split by pipe, normalize, and filter empty strings
            answers = {
                ans.lower().strip() for ans in row["answers"].split("|") if ans.strip()
            }
            questions.append({"question": question, "answers": answers})
    return questions


def normalize(text):
    """
    Normalize text for answer comparison.

    Removes punctuation, converts to lowercase, collapses whitespace, and strips.
    This allows flexible answer matching (e.g., "Paris" matches "paris!").

    Args:
        text (str or other): Text to normalize

    Returns:
        str: Normalized text (lowercase, no punctuation, single spaces, trimmed)
    """
    if not isinstance(text, str):
        return ""
    # Remove all non-word characters except whitespace
    text = re.sub(r"[^\w\s]", "", text.lower())
    # Collapse multiple spaces into single space
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ============================================================================
# MAIN BOT CLASS
# ============================================================================


class AsyncTriviaGameMaster:
    """
    Main trivia game bot class.

    Manages WhatsApp connection, question flow, answer validation,
    and leaderboard tracking. Uses threading locks for safe concurrent
    message handling.
    """

    def __init__(self, session_name, group_id):
        """
        Initialize the bot and connect to WhatsApp.

        Args:
            session_name (str): Name for the WhatsApp session (for persistence)
            group_id (str): WhatsApp group ID (format: "123-456@g.us")

        Raises:
            RuntimeError: If WhatsApp connection fails
        """
        self.group_id = group_id

        # Initialize WhatsApp client
        self.creator = Create(session=session_name)
        self.client = self.creator.start()

        if self.creator.state != "CONNECTED":
            raise RuntimeError(f"Connection failed: {self.creator.state}")

        # Thread safety lock for concurrent message handling
        self.lock = Lock()

        # ----- Per-question state (reset for each question) -----
        self.correct_answers = set()  # Set of valid answers (normalized)
        self.correct_respondents = []  # List of users who answered correctly
        self.seen_users = set()  # User IDs who have already answered
        self.current_question_msg_id = None  # Message ID of current question
        self.current_question_text = None  # Text of current question
        self.first_correct_message_id = None  # Message ID of first correct answer
        self.question_timestamp = None  # When question was sent (Unix timestamp)
        self.cutoff_timestamp = None  # Deadline for answers (Unix timestamp)

        # ----- Leaderboard (persists across questions) -----
        self.leaderboard_data = []  # List of {question_text, winners} dicts

        print("Bot connected (async)")

    # ========================================================================
    # GAME FLOW METHODS
    # ========================================================================

    async def run_question(
        self, question, answers, is_last_question=False, question_number=3
    ):
        """
        Run a complete question cycle: ask, wait, reveal, record.

        Flow:
            1. Send question to group
            2. Wait QUESTION_DURATION seconds
            3. Send "STOP" message
            4. Wait REP_DELAY seconds
            5. Send "REP" with answer (quotes first correct if any)
            6. If not last question: wait NEXT_DELAY, send "NEXT"
            7. Save results to leaderboard

        Args:
            question (str): The question text
            answers (set): Set of acceptable answers
            is_last_question (bool): Whether this is the final question
            question_number (int): Question number for display
        """
        # Reset state for new question (thread-safe)
        with self.lock:
            self.correct_answers = {a.lower().strip() for a in answers}
            self.correct_respondents = []
            self.seen_users = set()
            self.first_correct_message_id = None
            self.question_timestamp = None
            self.cutoff_timestamp = None

        # Send question to group
        msg = self.client.sendText(self.group_id, f"Q{question_number}: {question}")

        # Extract timestamp from WhatsApp message
        # This is more reliable than using time.time() due to network delays
        msg_timestamp = msg.get("t")
        if msg_timestamp is None:
            # Fallback if timestamp not available
            print("No WhatsApp timestamp found, using fallback...")
            msg_timestamp = int(time.time())

        # Store question metadata (thread-safe)
        with self.lock:
            self.current_question_msg_id = msg.get("id")
            self.current_question_text = question
            self.question_timestamp = msg_timestamp
            self.cutoff_timestamp = msg_timestamp + QUESTION_DURATION

        print(f"QUESTION: {question}")
        print(
            f"Question sent at timestamp: {msg_timestamp} ({time.strftime('%H:%M:%S', time.localtime(msg_timestamp))})"
        )
        print(
            f"Cutoff timestamp: {self.cutoff_timestamp} ({time.strftime('%H:%M:%S', time.localtime(self.cutoff_timestamp))})"
        )

        # Wait for answers (answers are processed by check_answer callback)
        await asyncio.sleep(QUESTION_DURATION)

        # Signal that time is up
        await self.send_stop()

        # Small buffer to process any in-flight messages
        await asyncio.sleep(0.5)

        # Reveal the answer
        await asyncio.sleep(REP_DELAY)
        await self.send_rep()

        # Move to next question (unless this was the last one)
        if not is_last_question:
            await asyncio.sleep(NEXT_DELAY)
            await self.send_next()
        else:
            # Save final question results without sending NEXT
            with self.lock:
                self.leaderboard_data.append(
                    {
                        "question_text": self.current_question_text,
                        "winners": self.correct_respondents.copy(),
                    }
                )
                print("(Last question - NEXT not sent)\n")

    async def send_stop(self):
        """Send STOP message to indicate time is up."""
        self.client.sendText(self.group_id, "STOP")
        print(f"STOP sent at {time.strftime('%H:%M:%S')}")

    async def send_rep(self):
        """
        Send REP (reply) message with the answer.

        If anyone answered correctly, quotes the first correct answer.
        Otherwise, lists all acceptable answers.
        """
        with self.lock:
            first_msg_id = self.first_correct_message_id
            answers_copy = self.correct_answers.copy()
            respondents_count = len(self.correct_respondents)

        if first_msg_id:
            # Quote the first correct answer
            self.client.reply(self.group_id, "REP", first_msg_id)
            print(f"REP (quoted) - {respondents_count} correct answer(s)")
        else:
            # No one got it right - show answers
            answers = " / ".join(sorted(answers_copy))
            self.client.sendText(self.group_id, f"REP: {answers}")
            print("REP (no correct answers)")

    async def send_next(self):
        """
        Send NEXT message and save results.

        Saves the current question to leaderboard and resets state
        for the next question.
        """
        self.client.sendText(self.group_id, "NEXT")
        print("NEXT sent\n")

        # Save results and reset state (thread-safe)
        with self.lock:
            self.leaderboard_data.append(
                {
                    "question_text": self.current_question_text,
                    "winners": self.correct_respondents.copy(),
                }
            )

            # Reset all per-question state
            self.current_question_msg_id = None
            self.current_question_text = None
            self.correct_answers = set()
            self.correct_respondents = []
            self.seen_users = set()
            self.first_correct_message_id = None
            self.question_timestamp = None
            self.cutoff_timestamp = None

    # ========================================================================
    # MESSAGE HANDLER
    # ========================================================================

    def check_answer(self, message):
        """
        Message callback to check if incoming message is a correct answer.

        This runs in the WhatsApp client's callback thread, so it uses
        locks for thread safety. Only counts answers that are:
        - From group members (not bot itself)
        - Sent after the question
        - Sent before the cutoff time
        - Correct according to normalized matching
        - From users who haven't already answered
        - Within the first 5 correct answers

        Args:
            message (dict): WhatsApp message object with keys:
                - fromMe (bool): If message is from bot
                - isGroupMsg (bool): If message is from a group
                - from (str): Group/user ID
                - body (str): Message text
                - t (int): Unix timestamp
                - sender (dict): Sender info {id, pushname}
                - id (str): Message ID
        """
        try:
            # Filter out irrelevant messages
            if (
                not message
                or message.get("fromMe")  # Ignore bot's own messages
                or not message.get("isGroupMsg")  # Only group messages
                or message.get("from") != self.group_id  # Only from target group
            ):
                return

            # Normalize and validate message body
            body = normalize(message.get("body"))
            if not body:
                return

            # Extract message timestamp
            msg_timestamp = message.get("t")
            if msg_timestamp is None:
                print("⚠ Message has no timestamp, skipping")
                return

            # All checks from here use shared state, so acquire lock
            with self.lock:
                # Check if we have an active question
                if self.question_timestamp is None or self.cutoff_timestamp is None:
                    return

                # Validate timing: message must be after question but before cutoff
                if msg_timestamp < self.question_timestamp:
                    # Message sent before question (shouldn't happen normally)
                    return

                if msg_timestamp > self.cutoff_timestamp:
                    # Message sent after deadline - reject but log it
                    print(
                        f"⏰ Late answer from {message.get('sender', {}).get('pushname', 'Someone')}: {body} "
                        f"(sent at {time.strftime('%H:%M:%S', time.localtime(msg_timestamp))}, "
                        f"cutoff was {time.strftime('%H:%M:%S', time.localtime(self.cutoff_timestamp))})"
                    )
                    return

                # Check if answer is correct
                if body not in self.correct_answers:
                    return

                # Extract sender information
                sender_info = message.get("sender", {})
                sender_id = str(sender_info.get("id", sender_info))
                sender_name = sender_info.get("pushname", "Someone")

                # Check if user already answered (prevent multiple answers)
                if sender_id in self.seen_users:
                    return

                # Check if we already have 5 winners (cap at 5)
                if len(self.correct_respondents) >= 5:
                    return

                # Save first correct message ID (for quoting in REP)
                if not self.first_correct_message_id:
                    self.first_correct_message_id = message.get("id")

                # Record the correct answer with timing information
                self.seen_users.add(sender_id)
                time_diff = msg_timestamp - self.question_timestamp
                self.correct_respondents.append(
                    {
                        "user_id": sender_id,
                        "name": sender_name,
                        "timestamp": msg_timestamp,
                        "response_time": time_diff,
                    }
                )

                # Log the correct answer
                print(
                    f"✓ Correct by {sender_name}: {body} "
                    f"(answered at {time.strftime('%H:%M:%S', time.localtime(msg_timestamp))}, "
                    f"+{time_diff:.1f}s after question)"
                )

        except Exception as e:
            # Catch and log any errors to prevent callback crashes
            print(f"Error in check_answer: {e}")
            traceback.print_exc()

    def start_listening(self):
        """
        Register the message callback to start processing answers.

        This sets up the bot to receive and check all incoming messages.
        """
        self.creator.client.onMessage(self.check_answer)
        print("Listening for answers...")

    # ========================================================================
    # LEADERBOARD METHODS
    # ========================================================================

    def save_leaderboard_csv(self):
        """
        Save the leaderboard with detailed timing to a CSV file.

        CSV format:
            Question | Winner1 | Time1 | ResponseTime1 | Winner2 | Time2 | ...

        Each winner gets 3 columns: name, timestamp, and response time.
        Up to 5 winners per question.
        """
        # Create thread-safe copy of data
        with self.lock:
            data_copy = [entry.copy() for entry in self.leaderboard_data]

        with open(LEADERBOARD_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Write header
            header = ["Question"]
            for i in range(1, 6):
                header += [f"Winner{i}", f"Time{i}", f"ResponseTime{i}"]
            writer.writerow(header)

            # Write each question's results
            for entry in data_copy:
                winners = entry["winners"]
                question_text = entry.get("question_text", "")
                row = [question_text]

                # Add winner data
                for w in winners:
                    row += [
                        w["name"],
                        time.strftime("%H:%M:%S", time.localtime(w["timestamp"])),
                        f"{w['response_time']:.1f}s",
                    ]

                # Pad row to consistent length (16 columns total)
                while len(row) < 16:  # 1 + 5*3 = 16 columns
                    row.append("")

                writer.writerow(row)

        print(f"Leaderboard saved to {LEADERBOARD_CSV}")

    def print_leaderboard(self):
        """
        Print a formatted leaderboard to the console.

        Shows each question with its winners in order, including
        response times.
        """
        # Create thread-safe copy of data
        with self.lock:
            data_copy = [entry.copy() for entry in self.leaderboard_data]

        print("\n" + "=" * 80)
        print("LEADERBOARD")
        print("=" * 80)

        for i, entry in enumerate(data_copy, 1):
            print(f"\nQ{i}: {entry['question_text']}")
            winners = entry["winners"]
            if winners:
                for j, w in enumerate(winners, 1):
                    print(f"  {j}. {w['name']} - {w['response_time']:.1f}s")
            else:
                print("  No correct answers")

        print("\n" + "=" * 80)


# ============================================================================
# MAIN EXECUTION
# ============================================================================


async def main():
    """
    Main function to run the trivia game.

    Loads questions, initializes bot, runs all questions in sequence,
    and handles leaderboard output.
    """

    # Load questions from CSV
    questions = load_questions_from_csv(CSV_PATH)
    if not questions:
        print("No questions loaded!")
        return

    # Initialize bot and start listening
    bot = AsyncTriviaGameMaster(SESSION_NAME, GROUP_ID)
    bot.start_listening()

    print(f"Loaded {len(questions)} questions")
    print("Starting trivia game...\n")

    # Run each question
    total_questions = len(questions)
    for i, q in enumerate(questions, start=1):
        is_last = i == total_questions
        await bot.run_question(
            q["question"], q["answers"], is_last_question=is_last, question_number=i
        )

    print("All questions completed!")

    # Display results
    bot.print_leaderboard()

    # Optionally save to CSV
    answer = input("\nSave leaderboard to CSV? (y/n): ").strip().lower()
    if answer == "y":
        bot.save_leaderboard_csv()

    print("Bot stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped.")
