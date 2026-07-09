"""
The "reference" DOM snapshots below represent what the target application's
pages looked like at the moment the test was authored (e.g. captured by a
recorder/crawler when the NL intent was compiled into steps). They are never
served by the live app -- they exist purely as ground truth we hand to the
compiler LLM so it can emit real selectors instead of hallucinating them.

The live app (see router.py) intentionally serves a DRIFTED version of the
orders page, so a deterministic step written against the reference DOM fails
against the live DOM. That mismatch is the "UI drift" this whole prototype
exists to demonstrate recovering from.
"""

LOGIN_PAGE_REFERENCE = """
<form id="login-form" action="/target/login" method="post">
  <label for="username">Username</label>
  <input id="username" name="username" type="text" />
  <label for="password">Password</label>
  <input id="password" name="password" type="password" />
  <button id="login-button" type="submit">Log in</button>
</form>
""".strip()

ORDERS_PAGE_REFERENCE = """
<div id="orders-page">
  <h1>Your Orders</h1>
  <div id="last-order-summary" class="order-card">
    <span class="order-id">Order #1042</span>
    <span class="order-item">Wireless Mouse</span>
    <span class="order-status">Delivered</span>
  </div>
</div>
""".strip()

APP_MANIFEST = f"""
Page: /target/login
{LOGIN_PAGE_REFERENCE}

Page: /target/orders (shown immediately after a successful login)
{ORDERS_PAGE_REFERENCE}
""".strip()
