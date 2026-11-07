// Attach the login credential to same-origin API requests only.
const apiFetch = (url, options = {}) => {
  const headers = new Headers(options.headers);
  const token = sessionStorage.getItem('access_token');
  if (token && new URL(url, location.href).origin === location.origin) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  return fetch(url, { ...options, headers });
};

const chatForm = document.getElementById('chat-form');
const messageInput = document.getElementById('message');
const chatWindow = document.getElementById('chat-window');
const loadingEl = document.getElementById('loading');
const videoSection = document.getElementById('video-suggestions');
const videoList = document.getElementById('video-list');
const imageSection = document.getElementById('image-suggestions');
const imageList = document.getElementById('image-list');
const pdfSection = document.getElementById('pdf-suggestions');
const pdfList = document.getElementById('pdf-list');
const matchedPdfSection = document.getElementById('matched-pdf-suggestions');
const matchedPdfList = document.getElementById('matched-pdf-list');
const questionList = document.getElementById('question-list');
const logoutButton = document.getElementById('logout-button');
const newSessionButton = document.getElementById('new-session-button');
const sessionListEl = document.getElementById('session-list');
const sessionSearchInput = document.getElementById('session-search');

if (messageInput) messageInput.dataset.defaultPlaceholder = messageInput.placeholder;

let currentSessionId = null;
let sessionCache = [];
let lastUserPrompt = '';
let lastQuizPayload = null;
let lastQuizPrompt = '';

const sanitizeMarkdown = (markdownText) => {
  const rawHtml = marked.parse(markdownText || '');
  return DOMPurify.sanitize(rawHtml, { USE_PROFILES: { html: true } });
};

document.addEventListener('DOMContentLoaded', () => {
  const closeBtn = document.getElementById('closeVideoBtn');
  const backdrop = document.querySelector('.video-backdrop');

  if (closeBtn) {
    closeBtn.addEventListener('click', closeVideo);
  }

  if (backdrop) {
    backdrop.addEventListener('click', closeVideo);
  }
});

const scrollToBottom = () => {
  chatWindow.scrollTop = chatWindow.scrollHeight;
};

const formatTimestamp = (timestamp) => {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

const extractMessageText = (message) => {
  if (!message) return '';
  const content = message.content ?? message;

  if (typeof content === 'string') return content;
  if (typeof content === 'object') {
    if (content.type === 'quiz' && typeof content.content === 'string') return content.content;
    if (typeof content?.node_response?.content === 'string') return content.node_response.content;
    if (typeof content.content === 'string') return content.content;
    if (typeof content.message === 'string') return content.message;
  }
  return '';
};

const extractQuizPayload = (message) => {
  if (!message) return null;
  const content = message.content ?? message;
  if (typeof content !== 'object') return null;

  if (content.type === 'quiz') return content;
  if (content.node_response && typeof content.node_response === 'object') {
    const nested = content.node_response.content;
    if (nested && typeof nested === 'object' && nested.type === 'quiz') return nested;
  }
  if (content.content && typeof content.content === 'object' && content.content.type === 'quiz') {
    return content.content;
  }
  return null;
};

const createMessage = (role, content, timestamp = '') => {
  const container = document.createElement('div');
  const normalizedRole = role === 'assistant' ? 'bot' : role;
  container.className = `message ${normalizedRole}`;

  const meta = document.createElement('div');
  meta.className = 'meta';
  meta.textContent = `${normalizedRole === 'user' ? 'You' : 'Marine Tutor AI'}${timestamp ? ' • ' + timestamp : ''}`;

  const bubble = document.createElement('div');
  bubble.className = 'bubble';

  if (normalizedRole === 'bot') {
    if (content instanceof HTMLElement) {
      bubble.appendChild(content);
    } else {
      bubble.innerHTML = sanitizeMarkdown(content);
    }
  } else {
    bubble.textContent = content;
  }

  container.appendChild(meta);
  container.appendChild(bubble);
  chatWindow.appendChild(container);
  scrollToBottom();
};

const renderVideoSuggestions = (videos = []) => {
  videoList.innerHTML = '';

  if (!Array.isArray(videos) || videos.length === 0) {
    videoSection.hidden = true;
    return;
  }

  videoSection.hidden = false;

  videos.forEach((video, index) => {
    const url = video.Url;
    const title = video.Title || `Video ${index + 1}`;
    const thumbnailSrc = video.Thumbnail || '/ui/images/video-placeholder.png';

    // ✅ DIV — NOT <a>
    const card = document.createElement('div');
    card.className = 'video-thumb';
    card.style.cursor = 'pointer';

    card.addEventListener('click', () => {
      openVideo(url); // ✅ popup only
    });

    const img = document.createElement('img');
    img.src = thumbnailSrc;
    img.alt = title;

    const info = document.createElement('div');
    info.className = 'video-thumb-title';
    info.textContent = title;

    card.appendChild(img);
    card.appendChild(info);
    videoList.appendChild(card);
  });
};
;

const normalizeMediaUrl = (item = {}) => item.Url || item.url || item.Link || item.link || item.href || '';

const normalizeMediaTitle = (item = {}, fallback) =>
  item.Title || item.title || item.About || item.about || fallback;

const renderImageSuggestions = (images = []) => {
  imageList.innerHTML = '';

  if (!Array.isArray(images) || images.length === 0) {
    console.debug('[Images] No image suggestions available', { images });
    if (imageSection) imageSection.hidden = true;
    return;
  }

  console.debug('[Images] Rendering suggestions', { count: images.length, images });
  if (imageSection) imageSection.hidden = false;

  images.forEach((image, index) => {
    const url = normalizeMediaUrl(image);
    if (!url) return;

    const title = normalizeMediaTitle(image, `Image ${index + 1}`);
    const card = document.createElement("div");
    card.className = "media-card";
    card.style.cursor = "pointer";

    card.addEventListener("click", () => {
      openImage(url); // ✅ popup
    });

    const img = document.createElement('img');
    img.src = url;
    img.alt = title;

    const titleEl = document.createElement('div');
    titleEl.className = 'media-title';
    titleEl.textContent = title;

    // if (image.About || image.about) {
    //   const meta = document.createElement('div');
    //   meta.className = 'media-meta';
    //   meta.textContent = image.About || image.about;
    //   card.appendChild(meta);
    // }

    card.appendChild(img);
    card.appendChild(titleEl);
    imageList.appendChild(card);
  });
};

const renderPdfSuggestions = (pdfs = []) => {
  pdfList.innerHTML = '';

  if (!Array.isArray(pdfs) || pdfs.length === 0) {
    console.debug('[PDFs] No pdf suggestions available', { pdfs });
    if (pdfSection) pdfSection.hidden = true;
    return;
  }

  console.debug('[PDFs] Rendering suggestions', { count: pdfs.length, pdfs });
  if (pdfSection) pdfSection.hidden = false;

  pdfs.forEach((pdf, index) => {
    const url = normalizeMediaUrl(pdf);
    if (!url) return;

    const title = normalizeMediaTitle(pdf, `PDF ${index + 1}`);
    const card = document.createElement("div");
    card.className = "media-card";
    card.style.cursor = "pointer";

    card.addEventListener("click", () => {
      openPdf(url); // ✅ popup
    });
    // const card = document.createElement('a');
    // card.className = 'media-card';
    // card.href = url;
    // card.target = '_blank';
    card.rel = 'noopener noreferrer';

    const titleEl = document.createElement('div');
    titleEl.className = 'media-title';
    titleEl.textContent = title;

    const meta = document.createElement('div');
    meta.className = 'media-meta';
    meta.textContent = pdf.About || pdf.about || 'Download reference PDF';

    card.appendChild(titleEl);
    // card.appendChild(meta);
    pdfList.appendChild(card);
  });
};

const renderMatchedPdfSuggestions = (chunks = []) => {
  if (!matchedPdfList) return;
  matchedPdfList.innerHTML = '';

  if (!Array.isArray(chunks) || chunks.length === 0) {
    if (matchedPdfSection) matchedPdfSection.hidden = true;
    return;
  }

  if (matchedPdfSection) matchedPdfSection.hidden = false;

  chunks.forEach((chunk) => {
    const url = chunk.link || chunk.url || '';
    const title = chunk.document || chunk.title || 'Referenced Document';
    const page = chunk.page || 1;
    const matchPct = chunk.match_pct || (chunk.score ? Math.round(chunk.score * 100) : null);
    const topic = chunk.topic_name || chunk.course_name || '';
    const preview = chunk.text_preview || '';
    const images = Array.isArray(chunk.images) ? chunk.images : [];

    const card = document.createElement('div');
    card.className = 'matched-pdf-card';

    const headerEl = document.createElement('div');
    headerEl.className = 'matched-pdf-header';

    const titleEl = document.createElement('div');
    titleEl.className = 'matched-pdf-title';
    titleEl.textContent = title;

    const badgesEl = document.createElement('div');
    badgesEl.className = 'matched-pdf-badges';

    const pageChip = document.createElement('span');
    pageChip.className = 'pdf-page-chip';
    pageChip.textContent = `Page ${page}`;
    badgesEl.appendChild(pageChip);

    if (matchPct) {
      const scoreChip = document.createElement('span');
      scoreChip.className = 'pdf-score-chip';
      scoreChip.textContent = `${matchPct}% Match`;
      badgesEl.appendChild(scoreChip);
    }

    headerEl.appendChild(titleEl);
    headerEl.appendChild(badgesEl);
    card.appendChild(headerEl);

    if (topic) {
      const topicEl = document.createElement('div');
      topicEl.className = 'matched-pdf-topic';
      topicEl.textContent = `📍 ${topic}`;
      card.appendChild(topicEl);
    }

    if (preview) {
      const snippetEl = document.createElement('div');
      snippetEl.className = 'matched-pdf-snippet';
      snippetEl.textContent = preview;
      card.appendChild(snippetEl);
    }


    card.addEventListener('click', () => {
      if (url) {
        openPdf(url, page);
      }
    });

    matchedPdfList.appendChild(card);
  });
};

const renderSuggestions = (suggestions = []) => {
  questionList.innerHTML = '';

  if (!Array.isArray(suggestions) || suggestions.length === 0) return;

  suggestions.forEach((suggestion) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'question-button suggestion-btn';
    btn.textContent = suggestion;
    btn.addEventListener('click', () => {
      messageInput.value = '';
      sendMessage(suggestion);
    });
    questionList.appendChild(btn);
  });
};

const renderQuestionSuggestions = (questions = []) => {
  renderSuggestions(questions);
};

// "Did you mean...?" - clickable options under the bot's clarifying question
const removeClarification = () => {
  document.querySelectorAll('.clarification-options').forEach((el) => el.remove());
};

const renderClarification = (clarification) => {
  removeClarification();
  const options = clarification && Array.isArray(clarification.options) ? clarification.options : [];
  if (options.length === 0) return;

  const wrap = document.createElement('div');
  wrap.className = 'clarification-options';

  options.forEach((opt) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = `clarification-chip clarification-${opt.kind || 'topic'}`;
    btn.textContent = opt.label;
    if (opt.hint) btn.title = opt.hint;
    btn.addEventListener('click', () => {
      if (opt.kind === 'other' || !opt.query) {
        // Let the user type their own refinement
        removeClarification();
        messageInput.placeholder = `Tell me more about "${clarification.term}"...`;
        messageInput.focus();
        return;
      }
      removeClarification();
      messageInput.value = '';
      sendMessage(opt.query, { skipClarification: true, displayText: opt.kind === 'general' ? opt.label : undefined });
    });
    wrap.appendChild(btn);
  });

  chatWindow.appendChild(wrap);
  scrollToBottom();
};

const clearSuggestions = () => {
  renderVideoSuggestions([]);
  renderImageSuggestions([]);
  renderPdfSuggestions([]);
  renderMatchedPdfSuggestions([]);
  renderQuestionSuggestions([]);
};

const toggleLoading = (show) => {
  if (!loadingEl) return;
  loadingEl.hidden = !show;
  loadingEl.classList.toggle('active', show);
  loadingEl.setAttribute('aria-busy', String(show));
  loadingEl.setAttribute('aria-hidden', String(!show));
};

const renderQuizMessage = (quizPayload) => {
  if (!quizPayload || !Array.isArray(quizPayload.quiz_items)) return;

  lastQuizPayload = quizPayload;

  const quizId = `quiz-${Date.now()}`;
  const wrapper = document.createElement('div');
  wrapper.className = 'quiz-block';

  const intro = document.createElement('p');
  intro.className = 'muted';
  intro.textContent = quizPayload.content || 'Quiz time!';
  wrapper.appendChild(intro);

  quizPayload.quiz_items.forEach((item, index) => {
    const card = document.createElement('div');
    card.className = 'question-card inline';

    const title = document.createElement('div');
    title.className = 'question-title';
    title.textContent = `${index + 1}. ${item.question}`;
    card.appendChild(title);

    const options = document.createElement('div');
    options.className = 'options';

    item.options.forEach((option, optIndex) => {
      const optionId = `${quizId}-${index}-${optIndex}`;
      const label = document.createElement('label');
      label.className = 'option-card';

      const radio = document.createElement('input');
      radio.type = 'radio';
      radio.name = `${quizId}-${index}`;
      radio.value = optIndex;
      radio.id = optionId;

      const marker = document.createElement('span');
      marker.className = 'radio-marker';

      const text = document.createElement('span');
      text.className = 'option-text';
      text.textContent = option;

      label.appendChild(radio);
      label.appendChild(marker);
      label.appendChild(text);

      radio.addEventListener('change', () => {
        options.querySelectorAll('.option-card').forEach((el) => el.classList.remove('selected'));
        label.classList.add('selected');
      });

      options.appendChild(label);
    });

    card.appendChild(options);
    wrapper.appendChild(card);
  });

  const actions = document.createElement('div');
  actions.className = 'quiz-actions';

  const submitBtn = document.createElement('button');
  submitBtn.type = 'button';
  submitBtn.className = 'btn primary small';
  submitBtn.textContent = 'Submit Quiz';

  const retakeBtn = document.createElement('button');
  retakeBtn.type = 'button';
  retakeBtn.className = 'btn ghost small';
  retakeBtn.textContent = 'Retake Quiz';

  const resultRow = document.createElement('div');
  resultRow.className = 'quiz-result muted';

  submitBtn.addEventListener('click', async () => {
    submitBtn.disabled = true;
    resultRow.textContent = 'Grading your answers...';
    try {
      const userAnswers = quizPayload.quiz_items.map((_, idx) => {
        const selected = wrapper.querySelector(`input[name="${quizId}-${idx}"]:checked`);
        return selected ? Number(selected.value) : -1;
      });

      const resp = await apiFetch('/quiz/grade', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ quiz_items: quizPayload.quiz_items, user_answers: userAnswers }),
      });

      if (!resp.ok) throw new Error('Unable to grade quiz');
      const grade = await resp.json();
      resultRow.innerHTML = '';

      const summary = document.createElement('div');
      summary.textContent = `You scored ${grade.score_percent}% (${grade.correct_count}/${grade.total}).`;
      resultRow.appendChild(summary);

      if (Array.isArray(grade.corrections) && grade.corrections.length > 0) {
        const heading = document.createElement('div');
        heading.textContent = 'Correct answers:';
        resultRow.appendChild(heading);

        const list = document.createElement('ul');
        list.className = 'quiz-corrections';

        grade.corrections.forEach((item, idx) => {
          const li = document.createElement('li');
          const correct = item.correct_answer || 'Not provided';
          const userChoice = item.user_answer || 'No answer';
          li.textContent = `Q${idx + 1}: Correct: ${correct} | You chose: ${userChoice}`;
          list.appendChild(li);
        });

        resultRow.appendChild(list);
      }
    } catch (error) {
      resultRow.textContent = error.message || 'Could not grade quiz. Please try again.';
    } finally {
      submitBtn.disabled = false;
    }
  });

  retakeBtn.addEventListener('click', () => {
    if (lastQuizPrompt) {
      sendMessage(lastQuizPrompt);
    }
  });

  actions.appendChild(submitBtn);
  actions.appendChild(retakeBtn);
  wrapper.appendChild(actions);
  wrapper.appendChild(resultRow);

  createMessage('bot', wrapper, formatTimestamp(new Date().toISOString()));
};

const applyLatestSuggestions = (messages = []) => {
  const assistantMessage = [...messages].reverse().find((msg) => msg && msg.role === 'assistant');

  if (!assistantMessage) {
    clearSuggestions();
    return;
  }

  const videos = assistantMessage.videos || assistantMessage.video_suggestions || assistantMessage.metadata?.videos || [];
  const images = assistantMessage.images || assistantMessage.metadata?.images || [];
  const pdfs = assistantMessage.pdfs || assistantMessage.metadata?.pdfs || [];
  const matchedPdfs = assistantMessage.matched_pdf_chunks || assistantMessage.metadata?.matched_pdf_chunks || [];
  const questions = assistantMessage.question_suggestions || assistantMessage.metadata?.question_suggestions || [];

  console.debug('[History] Applying latest media from history', {
    videos,
    images,
    pdfs,
    questions,
    assistantMessage,
  });

  renderVideoSuggestions(Array.isArray(videos) ? videos : []);
  renderImageSuggestions(Array.isArray(images) ? images : []);
  renderPdfSuggestions(Array.isArray(pdfs) ? pdfs : []);
  renderMatchedPdfSuggestions(Array.isArray(matchedPdfs) ? matchedPdfs : []);
  renderQuestionSuggestions(Array.isArray(questions) ? questions : []);
};
// video open popup
function openVideo(url) {
  const modal = document.getElementById("videoModal");
  const video = document.getElementById("popupVideo");

  video.src = url;
  video.load();
  modal.classList.remove("hidden");
  video.play();
}

function closeVideo() {
  const modal = document.getElementById("videoModal");
  const video = document.getElementById("popupVideo");

  if (!modal || !video) return;

  video.pause(); // ✅ stop playback
  video.currentTime = 0;
  video.removeAttribute("src"); // ✅ unload video
  video.load();

  modal.classList.add("hidden"); // ✅ hide popup
}

// Close handlers
document.getElementById("closeVideoBtn").onclick = closeVideo;
document.querySelector(".video-backdrop").onclick = closeVideo;

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeVideo();
});
// 🔥 GLOBAL CLICK INTERCEPTOR (VERY IMPORTANT)

// image open and close in popup

function openImage(url) {
  const modal = document.getElementById('imageModal');
  const img = document.getElementById('popupImage');

  if (!modal || !img) return;

  img.src = url;
  modal.classList.remove('hidden');
}

function closeImage() {
  const modal = document.getElementById('imageModal');
  const img = document.getElementById('popupImage');

  if (!modal || !img) return;

  img.src = '';
  modal.classList.add('hidden');
}


document.addEventListener('DOMContentLoaded', () => {
  const closeBtn = document.getElementById('closeImageBtn');
  const backdrop = document.querySelector('.image-backdrop');

  if (closeBtn) closeBtn.addEventListener('click', closeImage);
  if (backdrop) backdrop.addEventListener('click', closeImage);
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeImage();
  }
});

document.addEventListener(
  'click',
  function (e) {
    const link = e.target.closest('a');
    if (!link) return;

    const href = link.getAttribute('href');
    if (!href) return;

    // Intercept image links
    if (/\.(png|jpg|jpeg|gif|webp)$/i.test(href)) {
      e.preventDefault();
      e.stopPropagation();
      openImage(href);
    }
  },
  true
);

// pdf open and close in popup with page anchor support
function openPdf(url, page = null) {
  const modal = document.getElementById('pdfModal');
  const iframe = document.getElementById('popupPdf');

  if (!modal || !iframe) return;

  const baseUrl = (url || '').split('#')[0];
  const hashParts = ['toolbar=0', 'navpanes=0', 'scrollbar=0'];
  if (page) {
    hashParts.unshift(`page=${page}`);
  }
  iframe.src = `${baseUrl}#${hashParts.join('&')}`;

  modal.classList.remove('hidden');
}

function closePdf() {
  const modal = document.getElementById('pdfModal');
  const iframe = document.getElementById('popupPdf');

  if (!modal || !iframe) return;

  iframe.src = '';
  modal.classList.add('hidden');
}

// ✅ PDF close bindings
document.addEventListener('DOMContentLoaded', () => {
  const closeBtn = document.getElementById('closePdfBtn');
  const backdrop = document.querySelector('.pdf-backdrop');

  if (closeBtn) closeBtn.addEventListener('click', closePdf);
  if (backdrop) backdrop.addEventListener('click', closePdf);
});

// ESC key support for PDF
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closePdf();
  }
});


// document.addEventListener(
//   'click',
//   function (e) {
//     const link = e.target.closest('a');
//     if (!link) return;

//     const href = link.getAttribute('href');
//     if (!href) return;

//     if (href.toLowerCase().endsWith('.pdf')) {
//       e.preventDefault();
//       e.stopPropagation();
//       openPdf(href);
//     }
//   },
//   true
// );



const renderHistory = (messages = []) => {
  chatWindow.innerHTML = '';
  if (messages.length === 0) {
    showWelcomeCard();
    return;
  }

  removeWelcomeCard();
  messages
    .filter((msg) => msg && typeof msg === 'object' && msg.role && msg.content !== undefined)
    .forEach((msg) => {
      const quizPayload = extractQuizPayload(msg);
      if (quizPayload) {
        renderQuizMessage(quizPayload);
        return;
      }

      const text = extractMessageText(msg);
      const timestamp = formatTimestamp(msg.timestamp || msg?.content?.timestamp);
      if (!text) return;
      if (msg.role === 'assistant') {
        createMessage('assistant', text, timestamp);
      } else {
        createMessage('user', text, timestamp);
      }
    });
  applyLatestSuggestions(messages);

  // Restore pending "Did you mean...?" options if the last message asked one
  const lastMsg = messages[messages.length - 1];
  if (lastMsg && lastMsg.role === 'assistant' && lastMsg.clarification) {
    clearSuggestions();
    renderClarification(lastMsg.clarification);
  }
};

const sessionPreview = (session) => {
  const lastMessage = session.last_message;
  const text = extractMessageText(lastMessage) || 'No messages yet';
  return text.length > 80 ? `${text.slice(0, 80)}…` : text;
};

const renderSessions = (sessions = sessionCache, activeId = currentSessionId) => {
  sessionListEl.innerHTML = '';
  sessions.forEach((session) => {
    const card = document.createElement('div');
    card.className = `session-card${session.session_id === activeId ? ' active' : ''}`;
    card.dataset.id = session.session_id;

    const title = document.createElement('div');
    title.className = 'session-title';
    title.textContent = session.title || 'Untitled session';

    const meta = document.createElement('div');
    meta.className = 'session-meta';
    const updated = formatTimestamp(session.updated_at);
    meta.textContent = `${session.message_count || 0} msgs${updated ? ' • ' + updated : ''}`;

    const preview = document.createElement('div');
    preview.className = 'session-preview';
    preview.textContent = sessionPreview(session);

    card.appendChild(title);
    card.appendChild(meta);
    card.appendChild(preview);

    card.addEventListener('click', async () => {
      await selectSession(session.session_id);
    });

    sessionListEl.appendChild(card);
  });
};

const fetchSessions = async (searchTerm = '') => {
  const query = searchTerm ? `?search=${encodeURIComponent(searchTerm)}` : '';
  const response = await apiFetch(`/sessions${query}`, { credentials: 'include' });

  if (!response.ok) {
    throw new Error('Unable to fetch sessions');
  }

  sessionCache = await response.json();
  renderSessions(sessionCache, currentSessionId);

  if (!currentSessionId && sessionCache.length) {
    await selectSession(sessionCache[0].session_id);
  }
};

const selectSession = async (sessionId) => {
  try {
    const response = await apiFetch(`/sessions/${sessionId}`, { credentials: 'include' });
    if (!response.ok) {
      throw new Error('Unable to load session');
    }
    const data = await response.json();
    currentSessionId = data.session_id;

    sessionCache = sessionCache.map((session) =>
      session.session_id === data.session_id
        ? {
          ...session,
          title: data.title,
          updated_at: data.updated_at,
          created_at: data.created_at,
          message_count: data.message_count,
          last_message: data.last_message,
        }
        : session
    );

    renderSessions(sessionCache, currentSessionId);
    renderHistory(data.messages || []);
  } catch (error) {
    createMessage('bot', error.message || 'Unable to load session.');
  }
};

const createSession = async () => {
  const response = await apiFetch('/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({}),
  });

  if (!response.ok) {
    throw new Error('Unable to create a new session');
  }

  const data = await response.json();
  currentSessionId = data.session_id;
  sessionCache = [data, ...sessionCache];
  renderSessions(sessionCache, currentSessionId);
  chatWindow.innerHTML = '';
  clearSuggestions();
  showWelcomeCard();
  return data;
};

const ensureSession = async () => {
  if (currentSessionId) return currentSessionId;
  const session = await createSession();
  return session.session_id;
};

const sendMessage = async (messageText, { skipClarification = false, displayText } = {}) => {
  removeWelcomeCard();
  removeClarification();
  messageInput.placeholder = messageInput.dataset.defaultPlaceholder || messageInput.placeholder;
  lastUserPrompt = messageText;
  const sessionId = await ensureSession();
  createMessage('user', displayText || messageText, new Date().toLocaleTimeString());
  toggleLoading(true);

  try {
    const response = await apiFetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        content: messageText,
        session_id: sessionId,
        skip_clarification: skipClarification,
      }),
    });

    if (!response.ok) {
      const errText = (await response.text()) || 'The server could not process your request.';
      throw new Error(errText);
    }

    const data = await response.json();
    const nodeResponse = data.node_response || data;
    const quizPayload = extractQuizPayload(nodeResponse) || extractQuizPayload(data);
    const botMessage = nodeResponse.content || 'I did not receive a response.';
    const botTimestamp = new Date(nodeResponse.timestamp || Date.now()).toLocaleTimeString();
    const videos =
      nodeResponse.videos ||
      nodeResponse.video_suggestions ||
      nodeResponse.metadata?.videos ||
      [];
    const images = nodeResponse.images || nodeResponse.metadata?.images || [];
    const pdfs = nodeResponse.pdfs || nodeResponse.metadata?.pdfs || [];
    const matchedPdfs = nodeResponse.matched_pdf_chunks || nodeResponse.metadata?.matched_pdf_chunks || data.matched_pdf_chunks || [];

    console.debug('[Chat] Response received', {
      hasNodeResponse: Boolean(data.node_response),
      videoSuggestions: nodeResponse.video_suggestions,
      videos,
      images,
      pdfs,
      questionSuggestions: nodeResponse.question_suggestions,
      rawResponse: data,
    });

    if (quizPayload) {
      lastQuizPrompt = lastUserPrompt;
      renderQuizMessage(quizPayload);
    } else {
      createMessage('assistant', botMessage, botTimestamp);
    }
    renderVideoSuggestions(videos);
    renderImageSuggestions(images);
    renderPdfSuggestions(pdfs);
    renderMatchedPdfSuggestions(matchedPdfs);

    const clarification = nodeResponse.metadata?.clarification;
    if (clarification) {
      // chips live under the message; avoid duplicating them in the sidebar
      renderQuestionSuggestions([]);
      renderClarification(clarification);
    } else {
      renderQuestionSuggestions(nodeResponse.question_suggestions || []);
    }

    // FIXED: safely refresh sessions without breaking loader
    try {
      await fetchSessions(sessionSearchInput.value.trim());
    } catch (e) {
      console.warn('Session refresh failed but continuing', e);
    }

  } catch (error) {
    console.error('[Chat] Failed to send message', error);
    createMessage('assistant', `⚠️ ${error.message || 'Something went wrong. Please try again.'}`);
  } finally {
    toggleLoading(false);
  }
};

chatForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const text = messageInput.value.trim();
  if (!text) return;
  messageInput.value = '';
  await sendMessage(text);
});

logoutButton.addEventListener('click', async () => {
  try {
    await apiFetch('/logout', { method: 'POST', credentials: 'include' });
  } catch (error) {
    // ignore logout errors but continue redirect
  } finally {
    sessionStorage.removeItem('access_token');
    sessionStorage.removeItem('user_id');
    window.location.href = 'login.html';
  }
});

newSessionButton.addEventListener('click', async () => {
  try {
    await createSession();
  } catch (error) {
    createMessage('bot', error.message || 'Unable to start a new session.');
  }
});

sessionSearchInput.addEventListener('input', async (event) => {
  try {
    await fetchSessions(event.target.value.trim());
  } catch (error) {
    // silently ignore search errors
  }
});

window.addEventListener('load', async () => {

  // FIX 1 — hide loader on startup
  toggleLoading(false);

  try {
    const resp = await apiFetch('/api/v1/health', { credentials: 'include' });
    if (!resp.ok) {
      sessionStorage.removeItem('access_token');
    sessionStorage.removeItem('user_id');
    window.location.href = 'login.html';
      return;
    }
    await fetchSessions();
     // If no session selected or empty chat
    if (!currentSessionId) {
      showWelcomeCard();
    }

  } catch (error) {
    createMessage('bot', 'Unable to reach the server. Please ensure the backend is running.');
  }
});

messageInput.addEventListener('keydown', (event) => {
  // Ignore IME composition (important for Chrome)
  if (event.isComposing) return;

  // Enter without Shift = send
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault(); // stop newline

    // Trigger the SAME logic as clicking Send
    chatForm.requestSubmit();
  }
});

// for welcome banner 
const removeWelcomeCard = () => {
  const card = document.getElementById('welcome-card');
  if (card) card.remove();
};

const showWelcomeCard = () => {
  // prevent duplicates
  if (document.getElementById('welcome-card')) return;

  const card = document.createElement('div');
  card.id = 'welcome-card';
  card.className = 'welcome-card';

  card.innerHTML = `
    <div class="welcome-icons">
      <img src="/ui/assets/dolphin.png" alt="Dolphin" />
      <img src="/ui/assets/ship.png" alt="Academy" />
    </div>

    <h2>Dolphin | AI</h2>
    <h3>How can I help you today?</h3>

    <p>
      You can ask me anything. I can provide summaries, key takeaways and
      knowledge checks, as well as help you locate specific videos from our
      library and recommend training courses to enhance your skills.
    </p>
  `;

  chatWindow.appendChild(card);
};

document.addEventListener('contextmenu', (e) => {
  if (e.target.id === 'popupImage') {
    e.preventDefault(); // ❌ block right-click menu
  }
});

/* ===============================
   VIDEO LINK INTERCEPTOR (MP4)
   =============================== */
document.addEventListener(
  'click',
  function (e) {
    const link = e.target.closest('a');
    if (!link) return;

    const href = link.getAttribute('href');
    if (!href) return;

    // 🔒 Intercept only MP4 video links
    if (href.toLowerCase().endsWith('.mp4')) {
      e.preventDefault();
      e.stopPropagation();
      openVideo(href); // ✅ open popup instead of new tab
    }
  },
  true // ⚠️ capture phase (VERY IMPORTANT)
);

