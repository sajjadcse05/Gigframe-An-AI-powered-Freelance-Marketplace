from sklearn.linear_model import LinearRegression
import numpy as np

from gigs.models import Gig

# Cached in memory once trained, same reasoning as the embedding model —
# retraining on every single form load would be wasteful when the
# underlying gig data hasn't changed since the last training run.
_model = None
_category_list = None


def _train_model():
    """
    Trains a simple linear regression: given a gig's category (as a
    one-hot encoded number) and delivery_days, predict price. Trained
    on whatever real gig data currently exists in the database — with
    seed data in place, this has genuine variety to learn from.
    """
    global _model, _category_list

    gigs = list(Gig.objects.all())
    if len(gigs) < 5:
        # Not enough data to train anything meaningful yet.
        return None, None

    categories = sorted(set(g.category for g in gigs))
    category_index = {cat: i for i, cat in enumerate(categories)}

    X = []
    y = []
    for gig in gigs:
        # One-hot encode the category (e.g. "Web Development" -> [1,0,0,0,0,0])
        # plus delivery_days as a plain number — together these are the
        # two inputs the model uses to predict price.
        one_hot = [0] * len(categories)
        one_hot[category_index[gig.category]] = 1
        X.append(one_hot + [gig.delivery_days])
        y.append(float(gig.price))

    model = LinearRegression()
    model.fit(np.array(X), np.array(y))

    return model, categories


def get_model():
    global _model, _category_list
    if _model is None:
        _model, _category_list = _train_model()
    return _model, _category_list


def suggest_price(category, delivery_days):
    """
    Returns a (low, high) suggested price range for a gig/job with the
    given category and delivery time, or None if there isn't enough
    data yet to make a sensible suggestion.
    """
    model, categories = get_model()
    if model is None or category not in categories:
        return None

    category_index = {cat: i for i, cat in enumerate(categories)}
    one_hot = [0] * len(categories)
    one_hot[category_index[category]] = 1
    X = np.array([one_hot + [delivery_days]])

    predicted = model.predict(X)[0]
    predicted = max(predicted, 100)  # floor, so it never suggests a nonsensical negative/near-zero price

    # Present as a range (±20%) rather than one exact number — a single
    # precise figure looks falsely authoritative for a model trained on
    # this much data; a range is honest about the uncertainty.
    low = round(predicted * 0.8, -1)   # round to nearest 10
    high = round(predicted * 1.2, -1)
    return int(low), int(high)


def retrain():
    """Called after seed data changes, or can be run periodically — forces the next suggest_price() call to retrain from current data."""
    global _model, _category_list
    _model = None
    _category_list = None