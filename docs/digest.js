// Daily Digest Display - Clean, Minimal Design

let currentDigestLanguage = localStorage.getItem('digestLang') || 'en';

function renderDailyDigest(digest) {
  if (!digest || !digest.top_stories) return '';

  const isEnglish = currentDigestLanguage === 'en';

  // Platform labels - short
  const platformLabels = {
    'baidu_top': '百度',
    'weibo_hot': '微博',
    'tencent_wechat_hot': '微信',
    'xinhua_news': '新华',
    'thepaper_news': '澎湃',
    'ladymax_news': 'LADY'
  };

  // Build HTML - matching site's section style
  let html = `
    <section class="section digest-section">
      <div class="digest-header">
        <div class="digest-header-text">
          <h2 class="digest-title">${isEnglish ? 'DAILY DIGEST' : '今日要闻'}</h2>
          <div class="digest-subtitle">${isEnglish ?
            `${digest.time_label} • ${digest.metrics.cross_platform_stories} cross-platform stories` :
            `${digest.beijing_time} 北京 • ${digest.metrics.cross_platform_stories} 个跨平台热点`}
          </div>
        </div>
        <div class="language-toggle">
          <button class="${isEnglish ? 'active' : ''}" onclick="switchDigestLanguage('en')">EN</button>
          <button class="${!isEnglish ? 'active' : ''}" onclick="switchDigestLanguage('zh')">中文</button>
        </div>
      </div>

      <div class="digest-grid">`;

  // Render only first 5 stories as compact cards
  digest.top_stories.slice(0, 5).forEach((story, index) => {
    let summary = isEnglish ? story.summary : (story.summary_zh || story.summary);

    // Parse JSON string if summary is in JSON format
    if (summary && typeof summary === 'string' && summary.trim().startsWith('{')) {
      try {
        const parsed = JSON.parse(summary);
        summary = isEnglish ? parsed.en : (parsed.zh || parsed.en);
      } catch (e) {
        console.warn('Failed to parse summary JSON:', e);
      }
    }

    // Get meaningful preview - get first paragraph or sentence
    let summaryPreview = '';
    if (summary) {
      // Split by paragraphs (double newline) or single newlines
      const paragraphs = summary.split(/\n\n|\n/).filter(p => p.trim().length > 10);
      // Use first paragraph as preview
      summaryPreview = paragraphs[0] || summary.substring(0, 200);
    }

    html += `
      <div class="digest-card" id="story-${index}">
        <div class="digest-card-header">
          <span class="story-rank">#${story.rank}</span>
          <span class="story-weight" title="${isEnglish ? 'Weight' : '权重'}">${story.weight.toFixed(1)}</span>
          <div class="story-platforms">
            ${story.platforms.slice(0, 3).map(p => `
              <span class="platform-badge ${p}">${platformLabels[p] || p}</span>
            `).join('')}
          </div>
          <span class="story-category">${story.category}</span>
        </div>

        <h3 class="digest-card-title">
          ${isEnglish ? story.english_title : story.primary_title}
        </h3>

        <div class="digest-card-summary">
          ${summaryPreview || (isEnglish ? story.english_title : story.primary_title)}
        </div>

        ${summary && summary.split('\n').length > 1 ? `
        <div class="digest-card-footer">
          <button class="expand-summary" onclick="toggleStory(${index})">
            ${isEnglish ? '+ Read more' : '+ 展开'}
          </button>
        </div>` : ''}
      </div>`;
  });

  html += `
      </div>
    </section>`;

  return html;
}

function toggleStory(index) {
  const card = document.getElementById(`story-${index}`);
  const isExpanded = card.classList.contains('expanded');

  if (isExpanded) {
    card.classList.remove('expanded');
    // Re-render with preview only
    loadAndDisplayDigest();
  } else {
    card.classList.add('expanded');
    // Re-render with full content
    const digest = window.currentDigest;
    if (digest && digest.top_stories[index]) {
      const story = digest.top_stories[index];
      const isEnglish = currentDigestLanguage === 'en';
      let summary = isEnglish ? story.summary : (story.summary_zh || story.summary);

      // Parse JSON string if summary is in JSON format
      if (summary && typeof summary === 'string' && summary.trim().startsWith('{')) {
        try {
          const parsed = JSON.parse(summary);
          summary = isEnglish ? parsed.en : (parsed.zh || parsed.en);
        } catch (e) {
          console.warn('Failed to parse summary JSON:', e);
        }
      }

      const summaryElement = card.querySelector('.digest-card-summary');
      if (summaryElement && summary) {
        // Split by paragraphs and display as separate <p> elements
        const paragraphs = summary.split(/\n\n/).filter(p => p.trim());
        summaryElement.innerHTML = paragraphs.map(para =>
          `<p>${para.trim()}</p>`
        ).join('');
      }

      const button = card.querySelector('.expand-summary');
      if (button) {
        button.textContent = isEnglish ? '− Collapse' : '− 收起';
        button.setAttribute('onclick', `toggleStory(${index})`);
      }
    }
  }
}

function switchDigestLanguage(lang) {
  currentDigestLanguage = lang;
  localStorage.setItem('digestLang', lang);
  loadAndDisplayDigest();
}

async function loadAndDisplayDigest() {
  try {
    const digest = await loadJSON('data/daily_digest.json');
    window.currentDigest = digest; // Store for expand/collapse
    const container = document.getElementById('digest-container');
    if (container && digest) {
      container.innerHTML = renderDailyDigest(digest);
    }
  } catch (error) {
    console.error('Failed to load digest:', error);
  }
}

// Auto-load on page load
document.addEventListener('DOMContentLoaded', () => {
  loadAndDisplayDigest();
});