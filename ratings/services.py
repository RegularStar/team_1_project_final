from collections import Counter
from typing import Dict, Any

from .models import Rating


def certificate_rating_summary(certificate_id: int) -> Dict[str, Any]:
    qs = Rating.objects.filter(certificate_id=certificate_id)
    total = qs.count()

    if not total:
        return {"average": 0.0, "total": 0, "distribution": []}

    scores = [rating.perceived_score for rating in qs]
    average = sum(scores) / total if total else 0

    distribution_counter = Counter(scores)
    distribution = [
        {"score": score, "count": distribution_counter.get(score, 0)}
        for score in range(1, 11)
    ]

    return {
        "average": round(float(average), 1) if total else 0.0,
        "total": total,
        "distribution": distribution,
    }
