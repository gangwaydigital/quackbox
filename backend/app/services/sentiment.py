"""
Lightweight sentiment analysis using keyword scoring.
No AI model needed — runs instantly on the full archive.
"""
import re
from collections import defaultdict
from app.database import get_db

# Sentiment lexicon (simplified AFINN-style)
POSITIVE = {
    'good': 3, 'great': 4, 'excellent': 5, 'awesome': 5, 'amazing': 5,
    'wonderful': 4, 'fantastic': 5, 'love': 3, 'happy': 3, 'glad': 2,
    'thanks': 2, 'thank': 2, 'appreciate': 3, 'perfect': 4, 'excited': 4,
    'beautiful': 3, 'brilliant': 4, 'outstanding': 5, 'impressive': 4,
    'enjoy': 2, 'pleased': 3, 'delighted': 4, 'success': 3, 'congratulations': 4,
    'congrats': 3, 'well done': 4, 'nice': 2, 'cool': 2, 'like': 1,
    'helpful': 3, 'agree': 2, 'yes': 1, 'absolutely': 3, 'definitely': 2,
    'welcome': 2, 'cheers': 2, 'best': 2, 'superb': 4, 'thrilled': 4,
}

NEGATIVE = {
    'bad': -3, 'terrible': -5, 'horrible': -5, 'awful': -4, 'hate': -4,
    'angry': -3, 'upset': -3, 'disappointed': -3, 'frustrating': -4,
    'annoying': -3, 'problem': -2, 'issue': -1, 'bug': -2, 'error': -2,
    'fail': -3, 'failed': -3, 'broken': -3, 'wrong': -2, 'sorry': -1,
    'unfortunately': -2, 'concern': -2, 'worried': -2, 'urgent': -2,
    'critical': -2, 'blocked': -3, 'delay': -2, 'delayed': -2,
    'disagree': -2, 'no': -1, 'cannot': -1, "can't": -1, 'difficult': -2,
    'complicated': -2, 'confusing': -2, 'worse': -3, 'worst': -5,
}

URGENCY = {
    'asap': 5, 'urgent': 5, 'emergency': 5, 'immediately': 4,
    'critical': 4, 'deadline': 3, 'eod': 3, 'eow': 2, 'priority': 3,
    'important': 2, 'time-sensitive': 4, 'rush': 4,
}

WORD_RE = re.compile(r'\b[a-z]+(?:\'[a-z]+)?\b')


def score_text(text):
    """Score a single text string. Returns dict with pos, neg, urgency, compound."""
    if not text:
        return {"positive": 0, "negative": 0, "urgency": 0, "compound": 0, "label": "neutral"}

    words = WORD_RE.findall(text.lower())
    pos = sum(POSITIVE.get(w, 0) for w in words)
    neg = sum(abs(NEGATIVE.get(w, 0)) for w in words)
    urg = sum(URGENCY.get(w, 0) for w in words)

    # Normalize by text length
    word_count = max(len(words), 1)
    compound = (pos - neg) / (word_count ** 0.5)

    if compound > 1.5:
        label = "very positive"
    elif compound > 0.5:
        label = "positive"
    elif compound < -1.5:
        label = "very negative"
    elif compound < -0.5:
        label = "negative"
    else:
        label = "neutral"

    return {"positive": pos, "negative": neg, "urgency": urg, "compound": round(compound, 3), "label": label}


def analyze_archive_sentiment():
    """Batch analyze sentiment across the entire archive. Returns trends over time."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, strftime('%Y-%m', date_sent) as month, strftime('%Y', date_sent) as year,
                   subject, body_text, sender_email
            FROM emails
            WHERE date_sent IS NOT NULL AND (body_text IS NOT NULL OR subject IS NOT NULL)
            ORDER BY date_timestamp ASC
        """).fetchall()

    monthly = defaultdict(lambda: {"pos": 0, "neg": 0, "urg": 0, "count": 0, "compound_sum": 0})
    yearly = defaultdict(lambda: {"pos": 0, "neg": 0, "urg": 0, "count": 0, "compound_sum": 0})
    label_counts = defaultdict(int)
    sender_sentiment = defaultdict(lambda: {"compound_sum": 0, "count": 0})
    total_analyzed = 0

    for row in rows:
        text = ((row["subject"] or "") + " " + (row["body_text"] or ""))[:2000]
        score = score_text(text)
        month = row["month"]
        year = row["year"]

        if month:
            monthly[month]["pos"] += score["positive"]
            monthly[month]["neg"] += score["negative"]
            monthly[month]["urg"] += score["urgency"]
            monthly[month]["count"] += 1
            monthly[month]["compound_sum"] += score["compound"]

        if year:
            yearly[year]["pos"] += score["positive"]
            yearly[year]["neg"] += score["negative"]
            yearly[year]["urg"] += score["urgency"]
            yearly[year]["count"] += 1
            yearly[year]["compound_sum"] += score["compound"]

        label_counts[score["label"]] += 1

        if row["sender_email"]:
            sender_sentiment[row["sender_email"]]["compound_sum"] += score["compound"]
            sender_sentiment[row["sender_email"]]["count"] += 1

        total_analyzed += 1

    # Build monthly trend
    monthly_trend = []
    for m in sorted(monthly.keys()):
        d = monthly[m]
        avg = d["compound_sum"] / max(d["count"], 1)
        monthly_trend.append({
            "month": m, "avg_sentiment": round(avg, 3),
            "positive": d["pos"], "negative": d["neg"],
            "urgency": d["urg"], "count": d["count"]
        })

    yearly_trend = []
    for y in sorted(yearly.keys()):
        d = yearly[y]
        avg = d["compound_sum"] / max(d["count"], 1)
        yearly_trend.append({
            "year": y, "avg_sentiment": round(avg, 3),
            "positive": d["pos"], "negative": d["neg"],
            "urgency": d["urg"], "count": d["count"]
        })

    # Top positive/negative senders
    sender_scores = []
    for email, data in sender_sentiment.items():
        if data["count"] >= 5:
            sender_scores.append({
                "email": email, "count": data["count"],
                "avg_sentiment": round(data["compound_sum"] / data["count"], 3)
            })

    sender_scores.sort(key=lambda x: -x["avg_sentiment"])
    most_positive = sender_scores[:10]
    most_negative = list(reversed(sender_scores[-10:])) if len(sender_scores) > 10 else []

    return {
        "total_analyzed": total_analyzed,
        "label_distribution": dict(label_counts),
        "monthly_trend": monthly_trend,
        "yearly_trend": yearly_trend,
        "most_positive_senders": most_positive,
        "most_negative_senders": most_negative,
    }
