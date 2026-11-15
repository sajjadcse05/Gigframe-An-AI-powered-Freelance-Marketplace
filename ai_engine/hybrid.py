from .embeddings import get_embedding, compute_similarity
from .collaborative import get_acceptance_rate


def score_freelancer_for_job(freelancer, job, method="hybrid", alpha=0.7):
    """
    Scores one freelancer against one job using the requested method:
      - "content":       semantic similarity only
      - "collaborative": historical acceptance rate only
      - "hybrid":        weighted combination of both (alpha = weight on content)
    """
    content_score = 0.0
    if freelancer.embedding is not None:
        content_score = compute_similarity(freelancer.embedding, job.embedding)

    collaborative_score = get_acceptance_rate(freelancer)

    if method == "content":
        return content_score
    elif method == "collaborative":
        return collaborative_score
    else:  # hybrid
        return alpha * content_score + (1 - alpha) * collaborative_score


def rank_freelancers_for_job(job, freelancers, method="hybrid", alpha=0.7):
    """
    Ranks a list/queryset of Freelancers against one Job, using the
    given method. Returns freelancers sorted best-match first.
    """
    scored = [(f, score_freelancer_for_job(f, job, method=method, alpha=alpha)) for f in freelancers]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [f for f, score in scored]