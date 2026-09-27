"""Account profile and balance via the native /auth/me endpoint."""


def profile(client):
    return client.me()


def balance(client):
    me = client.me()
    sub = me.get('subscription', {}) or {}
    plan = sub.get('plan', {}) or {}
    user = me.get('user', {}) or {}
    return {
        'balance': sub.get('balance'),
        'available': sub.get('availableBalance'),
        'plan': plan.get('type'),
        'plan_price': plan.get('price'),
        'currency': plan.get('currency'),
        'payment': sub.get('paymentPlan'),
        'region': sub.get('region'),
        'user': user.get('name') or me.get('name'),
        'email': user.get('email') or me.get('email'),
    }
