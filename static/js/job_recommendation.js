(function () {
  const form = document.getElementById('job-recommendation-form');
  if (!form) {
    return;
  }

  const urlInput = document.getElementById('job-url');
  const contentInput = document.getElementById('job-content');
  const statusEl = document.getElementById('job-status');
  const resultSection = document.getElementById('job-result');
  const jobExcerptEl = document.getElementById('job-excerpt');
  const listEl = document.getElementById('recommendation-list');
  const submitBtn = document.getElementById('recommend-submit');
  const resetBtn = document.getElementById('recommend-reset');

  function setStatus(message, type) {
    if (!statusEl) return;
    statusEl.textContent = message || '';
    statusEl.classList.remove('is-loading', 'is-error');
    if (type) {
      statusEl.classList.add(type);
    }
  }

  function getCsrfToken() {
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : null;
  }

  function toggleForm(disabled) {
    if (submitBtn) submitBtn.disabled = disabled;
    if (resetBtn) resetBtn.disabled = disabled;
    if (contentInput) contentInput.disabled = disabled;
    if (urlInput) urlInput.disabled = disabled;
  }

  function clearResults() {
    if (resultSection) {
      resultSection.hidden = true;
    }
    if (jobExcerptEl) {
      jobExcerptEl.textContent = '';
    }
    if (listEl) {
      listEl.innerHTML = '';
    }
  }

  resetBtn?.addEventListener('click', () => {
    form.reset();
    clearResults();
    setStatus('', null);
    contentInput?.focus();
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const content = (contentInput?.value || '').trim();
    const url = (urlInput?.value || '').trim();

    if (!content) {
      setStatus('채용공고 내용을 입력해주세요.', 'is-error');
      contentInput?.focus();
      return;
    }

    clearResults();
    setStatus('추천 자격증을 분석하고 있어요...', 'is-loading');
    toggleForm(true);

    try {
      const response = await fetch('/api/ai/job-certificates/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        credentials: 'same-origin',
        body: JSON.stringify({
          url: url || null,
          content,
          max_results: 5,
        }),
      });

      if (!response.ok) {
        if (response.status === 401) {
          setStatus('로그인이 필요합니다. 다시 시도해주세요.', 'is-error');
        } else {
          const data = await response.json().catch(() => null);
          const detail = data?.detail || '추천 요청 중 오류가 발생했습니다.';
          setStatus(detail, 'is-error');
        }
        return;
      }

      const payload = await response.json();
      renderResult(payload);
      setStatus('추천 결과를 확인하세요.', null);
    } catch (error) {
      console.error('Job recommendation error', error);
      setStatus('네트워크 오류로 추천에 실패했어요. 잠시 후 다시 시도해주세요.', 'is-error');
    } finally {
      toggleForm(false);
    }
  });

  function renderResult(payload) {
    if (!resultSection || !listEl) {
      return;
    }
    const excerpt = (payload?.job_excerpt || '').trim();
    if (excerpt && jobExcerptEl) {
      jobExcerptEl.textContent = excerpt;
    } else if (jobExcerptEl) {
      jobExcerptEl.textContent = '채용공고 요약을 불러오지 못했습니다.';
    }

    listEl.innerHTML = '';
    const items = Array.isArray(payload?.recommendations) ? payload.recommendations : [];

    if (!items.length) {
      const empty = document.createElement('p');
      empty.className = 'empty';
      empty.textContent = '추천 가능한 자격증을 찾지 못했습니다.';
      listEl.appendChild(empty);
    } else {
      items.forEach((item) => {
        const certificate = item.certificate || {};
        const element = document.createElement('article');
        element.className = 'rec-item';

        const header = document.createElement('header');
        const title = document.createElement('h4');
        title.textContent = certificate.name || '이름 없는 자격증';

        const link = document.createElement('a');
        if (certificate.id != null) {
          link.href = `/certificates/${certificate.id}/`;
        } else {
          link.href = '#';
        }
        link.textContent = '상세 보기';

        const score = document.createElement('span');
        score.className = 'score';
        if (typeof item.score === 'number') {
          const percent = Math.round(item.score * 1000) / 10;
          score.textContent = `적합도 ${percent}%`;
        }

        header.appendChild(title);
        header.appendChild(link);
        if (score.textContent) {
          header.appendChild(score);
        }

        element.appendChild(header);

        const reasons = Array.isArray(item.reasons) ? item.reasons : [];
        if (reasons.length) {
          const list = document.createElement('ul');
          reasons.forEach((reason) => {
            const li = document.createElement('li');
            li.textContent = reason;
            list.appendChild(li);
          });
          element.appendChild(list);
        }

        listEl.appendChild(element);
      });
    }

    resultSection.hidden = false;
    resultSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
})();
