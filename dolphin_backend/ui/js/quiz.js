const quizContainer = document.getElementById('quiz-questions');
const submitButton = document.getElementById('submit-quiz');
const retakeButton = document.getElementById('retake-quiz');
const loadButton = document.getElementById('load-quiz');
const topicInput = document.getElementById('quiz-topic');
const topicLabel = document.getElementById('quiz-topic-label');
const resultPanel = document.getElementById('result-panel');
const scoreText = document.getElementById('score-text');
const percentageText = document.getElementById('percentage-text');
const detailedResults = document.getElementById('detailed-results');

let currentQuiz = null;

const createOption = (questionId, option, index) => {
  const optionId = `${questionId}-opt-${index}`;
  const wrapper = document.createElement('label');
  wrapper.className = 'option-card';
  wrapper.setAttribute('for', optionId);

  const input = document.createElement('input');
  input.type = 'radio';
  input.name = questionId;
  input.value = option;
  input.id = optionId;

  const marker = document.createElement('span');
  marker.className = 'radio-marker';

  const text = document.createElement('span');
  text.className = 'option-text';
  text.textContent = option;

  wrapper.appendChild(input);
  wrapper.appendChild(marker);
  wrapper.appendChild(text);

  input.addEventListener('change', () => {
    wrapper.classList.add('selected');
    document
      .querySelectorAll(`input[name="${questionId}"]`)
      .forEach((el) => el.closest('label').classList.remove('selected'));
    wrapper.classList.add('selected');
    checkAllAnswered();
  });

  return wrapper;
};

const renderQuestions = (quiz) => {
  quizContainer.innerHTML = '';
  quiz.questions.forEach((question, idx) => {
    const card = document.createElement('div');
    card.className = 'question-card';
    card.dataset.questionId = question.id;

    const header = document.createElement('div');
    header.className = 'question-title';
    header.innerHTML = `<span class="badge">Q${idx + 1}</span> ${question.question}`;

    const optionGroup = document.createElement('div');
    optionGroup.className = 'options';

    question.options.forEach((option, optionIdx) => {
      optionGroup.appendChild(createOption(question.id, option, optionIdx));
    });

    card.appendChild(header);
    card.appendChild(optionGroup);
    quizContainer.appendChild(card);
  });

  submitButton.disabled = true;
  retakeButton.hidden = true;
  resultPanel.hidden = true;
  resultPanel.classList.remove('fade-in');
};

const checkAllAnswered = () => {
  if (!currentQuiz) return;
  const answered = currentQuiz.questions.every((q) => {
    const selected = document.querySelector(`input[name="${q.id}"]:checked`);
    return Boolean(selected);
  });
  submitButton.disabled = !answered;
};

const loadQuiz = async (topic = 'Marine Engine') => {
  try {
    submitButton.disabled = true;
    resultPanel.hidden = true;
    retakeButton.hidden = true;
    quizContainer.innerHTML = '<p class="muted">Loading quiz...</p>';

    const response = await fetch('/quiz/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic }),
    });

    if (!response.ok) {
      throw new Error('Unable to generate quiz');
    }

    const quiz = await response.json();
    currentQuiz = quiz;
    topicLabel.textContent = `${topic} Quiz`;
    renderQuestions(quiz);
  } catch (error) {
    quizContainer.innerHTML = `<p class="error">${error.message || 'Failed to load quiz'}</p>`;
  }
};

const submitQuiz = async () => {
  if (!currentQuiz) return;
  const answers = {};

  currentQuiz.questions.forEach((q) => {
    const selected = document.querySelector(`input[name="${q.id}"]:checked`);
    if (selected) {
      answers[q.id] = selected.value;
    }
  });

  if (Object.keys(answers).length !== currentQuiz.questions.length) {
    return;
  }

  submitButton.disabled = true;

  const response = await fetch('/quiz/submit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ quiz_id: currentQuiz.quiz_id, answers }),
  });

  if (!response.ok) {
    quizContainer.insertAdjacentHTML('beforeend', '<p class="error">Could not submit quiz.</p>');
    submitButton.disabled = false;
    return;
  }

  const result = await response.json();
  renderResults(result);
};

const renderResults = (response) => {
  const { score, total, percentage, detailed } = response;
  scoreText.textContent = `${score}/${total}`;
  percentageText.textContent = `${percentage}%`;
  detailedResults.innerHTML = '';

  document.querySelectorAll('input[type="radio"]').forEach((input) => {
    input.disabled = true;
  });

  detailed.forEach((detail) => {
    const item = document.createElement('div');
    item.className = `result-item ${detail.is_correct ? 'correct' : 'incorrect'}`;
    item.innerHTML = `
      <div>
        <p class="eyebrow">${detail.is_correct ? 'Correct' : 'Incorrect'}</p>
        <p>Selected: <strong>${detail.selected || 'No answer'}</strong></p>
        <p>Correct: <strong>${detail.correct}</strong></p>
      </div>
    `;
    detailedResults.appendChild(item);

    const questionCard = document.querySelector(`[data-question-id="${detail.id}"]`);
    if (!questionCard) return;

    const correctOption = questionCard.querySelector(`input[value="${detail.correct}"]`);
    const selectedOption = detail.selected
      ? questionCard.querySelector(`input[value="${detail.selected}"]`)
      : null;

    questionCard.classList.add(detail.is_correct ? 'is-correct' : 'is-incorrect');

    if (correctOption) {
      correctOption.closest('label').classList.add('correct-answer');
    }

    if (selectedOption && !detail.is_correct) {
      selectedOption.closest('label').classList.add('incorrect-answer');
    }
  });

  resultPanel.hidden = false;
  void resultPanel.offsetWidth;
  resultPanel.classList.add('fade-in');
  retakeButton.hidden = false;
};

const retakeQuiz = () => {
  if (!currentQuiz) return;
  renderQuestions(currentQuiz);
};

loadButton.addEventListener('click', () => {
  const topic = topicInput.value.trim() || 'Marine Engine';
  loadQuiz(topic);
});

submitButton.addEventListener('click', submitQuiz);
retakeButton.addEventListener('click', retakeQuiz);

document.addEventListener('DOMContentLoaded', () => {
  loadQuiz(topicInput.value);
});
