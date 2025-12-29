import pytest
import asyncio
import time
from unittest.mock import Mock, patch, mock_open
from threading import Lock
import csv

# Import the functions and class to test
import sys
sys.path.insert(0, '.')
from trivia_bot import (
    load_questions_from_csv,
    normalize,
    AsyncTriviaGameMaster,
    QUESTION_DURATION
)


class TestQuestionLoading:
    """Tests for CSV question loading"""
    
    def test_load_questions_basic(self):
        """Test loading basic questions from CSV"""
        csv_content = """question,answers
What is 2+2?,4|four
Capital of France?,Paris|paris"""
        
        with patch('builtins.open', mock_open(read_data=csv_content)):
            questions = load_questions_from_csv('dummy.csv')
        
        assert len(questions) == 2
        assert questions[0]['question'] == 'What is 2+2?'
        assert '4' in questions[0]['answers']
        assert 'four' in questions[0]['answers']
        assert questions[1]['question'] == 'Capital of France?'
        assert 'paris' in questions[1]['answers']
    
    def test_load_questions_with_spaces(self):
        """Test that answers are properly stripped"""
        csv_content = """question,answers
Test question?, answer1 | answer2 | answer3 """
        
        with patch('builtins.open', mock_open(read_data=csv_content)):
            questions = load_questions_from_csv('dummy.csv')
        
        assert 'answer1' in questions[0]['answers']
        assert 'answer2' in questions[0]['answers']
        assert 'answer3' in questions[0]['answers']
    
    def test_load_questions_empty_answers(self):
        """Test handling of empty answer fields"""
        csv_content = """question,answers
Test question?,answer1||answer2"""
        
        with patch('builtins.open', mock_open(read_data=csv_content)):
            questions = load_questions_from_csv('dummy.csv')
        
        # Empty strings should be filtered out
        assert '' not in questions[0]['answers']
        assert len(questions[0]['answers']) == 2


class TestNormalize:
    """Tests for text normalization function"""
    
    def test_normalize_basic(self):
        """Test basic normalization"""
        assert normalize("Hello World") == "hello world"
    
    def test_normalize_punctuation(self):
        """Test punctuation removal"""
        assert normalize("Hello, World!") == "hello world"
        assert normalize("What's up?") == "whats up"
    
    def test_normalize_extra_spaces(self):
        """Test whitespace handling"""
        assert normalize("  hello   world  ") == "hello world"
    
    def test_normalize_special_chars(self):
        """Test special character removal"""
        assert normalize("hello@#$%world") == "helloworld"
    
    def test_normalize_non_string(self):
        """Test handling of non-string input"""
        assert normalize(None) == ""
        assert normalize(123) == ""


class TestAsyncTriviaGameMaster:
    """Tests for the main bot class"""
    
    @pytest.fixture
    def mock_creator(self):
        """Create a mock WPP_Whatsapp creator"""
        creator = Mock()
        creator.state = 'CONNECTED'
        creator.client = Mock()
        return creator
    
    @pytest.fixture
    def bot(self, mock_creator):
        """Create a bot instance with mocked dependencies"""
        with patch('trivia_bot.Create', return_value=mock_creator):
            bot = AsyncTriviaGameMaster('test_session', 'test_group')
            return bot
    
    def test_initialization(self, mock_creator):
        """Test bot initialization"""
        with patch('trivia_bot.Create', return_value=mock_creator):
            bot = AsyncTriviaGameMaster('test_session', 'test_group')
            
            assert bot.group_id == 'test_group'
            assert isinstance(bot.lock, type(Lock()))
            assert bot.correct_answers == set()
            assert bot.correct_respondents == []
            assert bot.leaderboard_data == []
    
    def test_initialization_connection_failure(self):
        """Test that initialization fails with bad connection"""
        mock_creator = Mock()
        mock_creator.state = 'DISCONNECTED'
        mock_creator.start.return_value = Mock()
        
        with patch('trivia_bot.Create', return_value=mock_creator):
            with pytest.raises(RuntimeError, match="Connection failed"):
                AsyncTriviaGameMaster('test_session', 'test_group')
    
    def test_check_answer_correct(self, bot):
        """Test checking a correct answer"""
        # Setup question state
        current_time = int(time.time())
        bot.question_timestamp = current_time
        bot.cutoff_timestamp = current_time + QUESTION_DURATION
        bot.correct_answers = {'paris', 'france'}
        
        # Create a mock message
        message = {
            'fromMe': False,
            'isGroupMsg': True,
            'from': 'test_group',
            'body': 'Paris',
            't': current_time + 5,
            'sender': {
                'id': 'user123',
                'pushname': 'TestUser'
            },
            'id': 'msg123'
        }
        
        bot.check_answer(message)
        
        assert len(bot.correct_respondents) == 1
        assert bot.correct_respondents[0]['name'] == 'TestUser'
        assert bot.correct_respondents[0]['user_id'] == 'user123'
        assert bot.first_correct_message_id == 'msg123'
    
    def test_check_answer_incorrect(self, bot):
        """Test checking an incorrect answer"""
        current_time = int(time.time())
        bot.question_timestamp = current_time
        bot.cutoff_timestamp = current_time + QUESTION_DURATION
        bot.correct_answers = {'paris'}
        
        message = {
            'fromMe': False,
            'isGroupMsg': True,
            'from': 'test_group',
            'body': 'London',
            't': current_time + 5,
            'sender': {'id': 'user123', 'pushname': 'TestUser'}
        }
        
        bot.check_answer(message)
        
        assert len(bot.correct_respondents) == 0
    
    def test_check_answer_too_late(self, bot):
        """Test that late answers are rejected"""
        current_time = int(time.time())
        bot.question_timestamp = current_time
        bot.cutoff_timestamp = current_time + QUESTION_DURATION
        bot.correct_answers = {'paris'}
        
        message = {
            'fromMe': False,
            'isGroupMsg': True,
            'from': 'test_group',
            'body': 'Paris',
            't': current_time + QUESTION_DURATION + 5,  # After cutoff
            'sender': {'id': 'user123', 'pushname': 'TestUser'}
        }
        
        bot.check_answer(message)
        
        assert len(bot.correct_respondents) == 0
    
    def test_check_answer_before_question(self, bot):
        """Test that answers before question are rejected"""
        current_time = int(time.time())
        bot.question_timestamp = current_time
        bot.cutoff_timestamp = current_time + QUESTION_DURATION
        bot.correct_answers = {'paris'}
        
        message = {
            'fromMe': False,
            'isGroupMsg': True,
            'from': 'test_group',
            'body': 'Paris',
            't': current_time - 10,  # Before question
            'sender': {'id': 'user123', 'pushname': 'TestUser'}
        }
        
        bot.check_answer(message)
        
        assert len(bot.correct_respondents) == 0
    
    def test_check_answer_duplicate_user(self, bot):
        """Test that users can't answer twice"""
        current_time = int(time.time())
        bot.question_timestamp = current_time
        bot.cutoff_timestamp = current_time + QUESTION_DURATION
        bot.correct_answers = {'paris', 'france'}
        
        # First answer
        message1 = {
            'fromMe': False,
            'isGroupMsg': True,
            'from': 'test_group',
            'body': 'Paris',
            't': current_time + 5,
            'sender': {'id': 'user123', 'pushname': 'TestUser'},
            'id': 'msg1'
        }
        
        # Second answer from same user
        message2 = {
            'fromMe': False,
            'isGroupMsg': True,
            'from': 'test_group',
            'body': 'France',
            't': current_time + 7,
            'sender': {'id': 'user123', 'pushname': 'TestUser'},
            'id': 'msg2'
        }
        
        bot.check_answer(message1)
        bot.check_answer(message2)
        
        # Should only have one correct response
        assert len(bot.correct_respondents) == 1
    
    def test_check_answer_max_five_winners(self, bot):
        """Test that only 5 winners are recorded"""
        current_time = int(time.time())
        bot.question_timestamp = current_time
        bot.cutoff_timestamp = current_time + QUESTION_DURATION
        bot.correct_answers = {'paris'}
        
        # Send 6 correct answers
        for i in range(6):
            message = {
                'fromMe': False,
                'isGroupMsg': True,
                'from': 'test_group',
                'body': 'Paris',
                't': current_time + i + 1,
                'sender': {'id': f'user{i}', 'pushname': f'User{i}'},
                'id': f'msg{i}'
            }
            bot.check_answer(message)
        
        # Should only have 5 winners
        assert len(bot.correct_respondents) == 5
    
    def test_check_answer_ignores_own_messages(self, bot):
        """Test that bot's own messages are ignored"""
        current_time = int(time.time())
        bot.question_timestamp = current_time
        bot.cutoff_timestamp = current_time + QUESTION_DURATION
        bot.correct_answers = {'paris'}
        
        message = {
            'fromMe': True,  # Bot's own message
            'isGroupMsg': True,
            'from': 'test_group',
            'body': 'Paris',
            't': current_time + 5,
            'sender': {'id': 'bot', 'pushname': 'Bot'}
        }
        
        bot.check_answer(message)
        
        assert len(bot.correct_respondents) == 0
    
    def test_check_answer_ignores_non_group(self, bot):
        """Test that non-group messages are ignored"""
        current_time = int(time.time())
        bot.question_timestamp = current_time
        bot.cutoff_timestamp = current_time + QUESTION_DURATION
        bot.correct_answers = {'paris'}
        
        message = {
            'fromMe': False,
            'isGroupMsg': False,  # Not a group message
            'from': 'test_group',
            'body': 'Paris',
            't': current_time + 5,
            'sender': {'id': 'user123', 'pushname': 'TestUser'}
        }
        
        bot.check_answer(message)
        
        assert len(bot.correct_respondents) == 0
    
    def test_save_leaderboard_csv(self, bot, tmp_path):
        """Test saving leaderboard to CSV"""
        # Setup test data
        bot.leaderboard_data = [
            {
                'question_text': 'What is 2+2?',
                'winners': [
                    {'name': 'Alice', 'timestamp': 1234567890, 'response_time': 2.5},
                    {'name': 'Bob', 'timestamp': 1234567892, 'response_time': 4.5}
                ]
            }
        ]
        
        # Save to temp file
        test_file = tmp_path / "test_leaderboard.csv"
        with patch('trivia_bot.LEADERBOARD_CSV', str(test_file)):
            bot.save_leaderboard_csv()
        
        # Read and verify
        with open(test_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        assert len(rows) == 2  # Header + 1 data row
        assert rows[0][0] == 'Question'
        assert rows[1][0] == 'What is 2+2?'
        assert rows[1][1] == 'Alice'
        assert rows[1][4] == 'Bob'
    
    @pytest.mark.asyncio
    async def test_run_question_flow(self, bot):
        """Test the complete question flow"""
        bot.client.sendText = Mock(return_value={'id': 'msg123', 't': int(time.time())})
        bot.client.reply = Mock()
        
        # Mock the async delays to run faster
        with patch('asyncio.sleep', return_value=asyncio.sleep(0.01)):
            await bot.run_question(
                "Test question?",
                ["answer1", "answer2"],
                is_last_question=True,
                question_number=1
            )
        
        # Verify messages were sent
        assert bot.client.sendText.call_count >= 2  # Question + STOP
        
        # Verify leaderboard was updated
        assert len(bot.leaderboard_data) == 1
        assert bot.leaderboard_data[0]['question_text'] == "Test question?"


class TestIntegration:
    """Integration tests for the complete workflow"""
    
    @pytest.mark.asyncio
    async def test_full_game_flow(self, tmp_path):
        """Test a complete game with multiple questions"""
        # Create test questions file
        questions_file = tmp_path / "questions.csv"
        with open(questions_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['question', 'answers'])
            writer.writerow(['What is 2+2?', '4|four'])
            writer.writerow(['Capital of France?', 'Paris|paris'])
        
        questions = load_questions_from_csv(str(questions_file))
        assert len(questions) == 2
        
        # Create mock bot
        mock_creator = Mock()
        mock_creator.state = 'CONNECTED'
        mock_creator.client = Mock()
        mock_creator.client.sendText = Mock(return_value={'id': 'msg123', 't': int(time.time())})
        mock_creator.start = Mock(return_value=mock_creator.client)
        
        with patch('trivia_bot.Create', return_value=mock_creator):
            bot = AsyncTriviaGameMaster('test_session', 'test_group')
            
            # Run questions
            with patch('asyncio.sleep', return_value=asyncio.sleep(0.01)):
                for i, q in enumerate(questions, start=1):
                    await bot.run_question(
                        q['question'],
                        q['answers'],
                        is_last_question=(i == len(questions)),
                        question_number=i
                    )
            
            # Verify leaderboard has all questions
            assert len(bot.leaderboard_data) == 2