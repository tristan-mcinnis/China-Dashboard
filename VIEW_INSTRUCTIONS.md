# 🎯 Local Preview Instructions

## ✅ Server is Running!

Your China Dashboard with the new Daily Digest is now running locally.

### 📱 How to View:

1. **Open your browser and go to:**
   ```
   http://localhost:8000
   ```

2. **What you'll see:**

### Top of Page - Daily Digest Section:

```
┌─────────────────────────────────────────────────────────┐
│ 📊 Today's Key Stories                      [EN] [中文]  │
│ Evening Digest • 19:05 Beijing                          │
│ 10 cross-platform stories                               │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ #1  36.4  [百度][微信][微博]  BUSINESS                  │
│                                                          │
│ Wang Jianlin Faces Consumption Restrictions...          │
│                                                          │
│ Dalian Wanda Group and its founder Wang Jianlin have   │
│ been placed under consumption restrictions following    │
│ a court enforcement action involving 186 million yuan.  │
│ The restrictions prohibit luxury spending including...  │
│                                                          │
│ This development reflects ongoing challenges in China's │
│ property sector and signals continued deleveraging...   │
│                                                          │
│ ▾ Show appearances (3)                                  │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ #2  14.1  [百度][微信]  POLITICS                        │
│                                                          │
│ Pomegranate Seeds: Xi's Metaphor for Ethnic Unity      │
│                                                          │
│ President Xi Jinping has repeatedly used the           │
│ pomegranate seed metaphor to emphasize ethnic unity... │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Features to Test:

1. **Language Toggle:**
   - Click `[中文]` button → All summaries switch to Chinese
   - Click `[EN]` button → All summaries switch to English
   - Your choice is saved and persists on refresh

2. **Platform Badges:**
   - 百度 (Blue) - Baidu trending
   - 微博 (Red) - Weibo hot
   - 微信 (Green) - WeChat/Tencent

3. **Category Colors:**
   - BUSINESS (Yellow)
   - POLITICS (Pink)
   - MILITARY (Blue)
   - WEATHER (Green)
   - INTERNATIONAL (Purple)

4. **Weight Scores:**
   - Higher number = more important story
   - Hover over score for tooltip

5. **Expandable Details:**
   - Click "Show appearances" to see platform rankings

### Below the Digest:

The rest of your dashboard remains unchanged:
- Markets & FX section
- Trending topics from each platform
- Weather strip at top
- Dark mode toggle

## 🎨 Design Notes:

- **Gradient Header**: Purple-to-pink gradient makes digest stand out
- **Card Design**: Clean white cards with proper shadows
- **Responsive**: Works on mobile and desktop
- **Typography**: Uses your Inter font for consistency
- **Bilingual**: Full Chinese/English toggle support

## 🛑 To Stop the Server:

When you're done viewing, run:
```bash
pkill -f "python -m http.server"
```

## 📸 What It Should Look Like:

The digest appears as the FIRST thing users see when they visit your dashboard, giving them an immediate understanding of the day's most important China news stories with proper context and bilingual summaries.

The weight-based ranking ensures the most cross-platform viral stories appear first, while the summaries provide actual context (not just headlines).

---

**Go ahead and open http://localhost:8000 in your browser now!**