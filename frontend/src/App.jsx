import { useMemo, useRef, useState } from "react";
import CheckoutForm from "./components/CheckoutForm";
import "./App.css";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

function getChatUrl() {
  if (!API_BASE) return "/api/chat";
  if (API_BASE.endsWith("/api")) return `${API_BASE}/chat`;
  return `${API_BASE}/api/chat`;
}

const starterPrompts = [
  "I need groceries for this week under Rs. 10,000",
  "Mage amma ge birthday ekata gift ekak ona",
  "I broke up with my girlfriend… I need to send flowers",
  "Find me a useful laptop accessory",
  "මට birthday gift එකක් තෝරලා දෙන්න",
];

function makeSessionId() {
  return `kapruka-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function getNumericPrice(price) {
  if (!price) return 0;

  if (typeof price === "number") {
    return price;
  }

  if (typeof price === "object") {
    const amount = price.amount || price.value || price.price || 0;
    return Number(amount || 0);
  }

  const text = String(price);

  const amountMatch = text.match(/['"]?amount['"]?\s*:\s*([0-9.]+)/i);
  if (amountMatch) {
    return Number(amountMatch[1] || 0);
  }

  const raw = text.replace(/[^\d.]/g, "");
  return Number(raw || 0);
}

function formatPrice(price) {
  if (!price) return "Price available in Kapruka";

  if (typeof price === "number") {
    return `LKR ${price.toLocaleString()}`;
  }

  if (typeof price === "object") {
    const amount = price.amount || price.value || price.price;
    const currency = price.currency || "LKR";

    if (amount) {
      return `${currency} ${Number(amount).toLocaleString()}`;
    }

    return "Price available in Kapruka";
  }

  const text = String(price).trim();

  const amountMatch = text.match(/['"]?amount['"]?\s*:\s*([0-9.]+)/i);
  const currencyMatch = text.match(
    /['"]?currency['"]?\s*:\s*['"]?([A-Z]{3})['"]?/i,
  );

  if (amountMatch) {
    const amount = Number(amountMatch[1] || 0);
    const currency = currencyMatch?.[1] || "LKR";
    return `${currency} ${amount.toLocaleString()}`;
  }

  return text
    .replace(/[{}]/g, "")
    .replace(/['"]/g, "")
    .replace(/amount\s*:/gi, "")
    .replace(/currency\s*:\s*/gi, "")
    .replace(/\s+/g, " ")
    .trim();
}

function getProductKey(product, index) {
  return `${product.id || product.url || product.name || "product"}-${index}`;
}

function getProductImage(product) {
  return (
    product.image ||
    product.image_url ||
    product.imageUrl ||
    product.thumbnail ||
    ""
  );
}

function App() {
  const [sessionId] = useState(makeSessionId);
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text: "Ayubowan! I’m your Kapruka shopping buddy. Tell me what you need — groceries, gifts, electronics, flowers, cakes, or even a last-minute rescue mission.",
      products: [],
      quickReplies: starterPrompts.slice(0, 3),
    },
  ]);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [cart, setCart] = useState([]);
  const [showCheckoutForm, setShowCheckoutForm] = useState(false);
  const [failedImages, setFailedImages] = useState({});
  const chatEndRef = useRef(null);

  const cartTotal = useMemo(() => {
    return cart.reduce((sum, item) => {
      return sum + getNumericPrice(item.price);
    }, 0);
  }, [cart]);

  function scrollToBottom() {
    setTimeout(() => {
      chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 80);
  }

  function addToCart(product) {
    setCart((prev) => [...prev, product]);
  }

  function removeFromCart(index) {
    setCart((prev) => prev.filter((_, i) => i !== index));
  }

  async function sendMessage(customText) {
    const text = (customText || input).trim();
    if (!text || loading) return;

    setInput("");
    setLoading(true);

    const userMessage = {
      role: "user",
      text,
      products: [],
      quickReplies: [],
    };

    setMessages((prev) => [...prev, userMessage]);
    scrollToBottom();

    try {
      const res = await fetch(getChatUrl(), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          session_id: sessionId,
          message: text,
        }),
      });

      if (!res.ok) {
        throw new Error("Backend request failed");
      }

      const data = await res.json();

      const assistantMessage = {
        role: "assistant",
        text: data.reply,
        products: data.products || [],
        checkoutUrl: data.checkout_url || null,
        quickReplies: data.quick_replies || [],
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: "Aiyo, I could not reach the shopping agent right now. Check whether the backend is running on port 8000.",
          products: [],
          quickReplies: ["Try again", "Search flowers", "Search groceries"],
        },
      ]);
    } finally {
      setLoading(false);
      scrollToBottom();
    }
  }

  function checkoutWithAgent() {
    if (cart.length === 0) return;
    setShowCheckoutForm(true);
  }

  function handleCheckoutSubmit(details) {
    setShowCheckoutForm(false);

    const cartText = details.cart
      .map(
        (item, index) =>
          `${index + 1}. ${item.name} - ${formatPrice(item.price)}`,
      )
      .join("\n");

    const checkoutText = `I want to checkout these Kapruka cart items:
${cartText}

Approximate total: ${
      details.cartTotal > 0
        ? `${details.currency} ${details.cartTotal.toLocaleString()}`
        : "Pending"
    }
Currency: ${details.currency}
Order type: ${details.orderType}

Recipient details:
Name: ${details.recipientName}
Phone: ${details.recipientPhone}
Email: ${details.recipientEmail || "Not provided"}

Delivery details:
City: ${details.deliveryCity}
Address: ${details.deliveryAddress}
Preferred delivery date: ${details.deliveryDate}

Sender details:
Name: ${details.senderName}
Phone: ${details.senderPhone}
Email: ${details.senderEmail || "Not provided"}

Gift message:
${details.giftMessage || "No gift message"}

Please check delivery availability first for this city, address, and preferred date. If delivery is possible, help me continue to Kapruka guest checkout.`;

    sendMessage(checkoutText);
  }

  return (
    <main className="app-shell">
      <section className="left-panel">
        <div>
          <div className="brand-pill">Kapruka AI Agent</div>

          <h1>
            Shopping that feels
            <span> human.</span>
          </h1>

          <p className="hero-copy">
            A full-screen AI shopping concierge for everyday needs, gifts,
            delivery planning, and checkout.
          </p>

          <div className="mode-grid">
            <button
              onClick={() => sendMessage("I want to buy groceries for myself")}
            >
              🛒 Everyday shopping
            </button>

            <button
              onClick={() => sendMessage("I need to send a gift to someone")}
            >
              🎁 Gift mode
            </button>

            <button onClick={() => sendMessage("මට Sinhala වලින් help කරන්න")}>
              🇱🇰 Sinhala
            </button>

            <button
              onClick={() =>
                sendMessage("Tanglish walin shopping help ekak denna")
              }
            >
              💬 Tanglish
            </button>
          </div>
        </div>

        <div className="demo-card">
          <p className="demo-label">Try this</p>
          <p>
            “I forgot my anniversary. I need something romantic delivered
            tomorrow.”
          </p>
        </div>
      </section>

      <section className="chat-panel">
        <div className="chat-header">
          <div>
            <p className="eyebrow">Live shopping assistant</p>
            <h2>Kapruka Concierge</h2>
          </div>

          <div className="status-dot">
            <span></span>
            Online
          </div>
        </div>

        <div className="messages">
          {messages.map((msg, index) => {
            const hasProducts = msg.products?.length > 0;
            const hasCheckout = Boolean(msg.checkoutUrl);
            const hasQuickReplies = msg.quickReplies?.length > 0;

            return (
              <div
                key={index}
                className={`message-row ${msg.role} ${hasProducts ? "has-products" : ""}`}
              >
                <div className={`message-stack ${msg.role}`}>
                  {msg.text && (
                    <div className="bubble message-bubble-only">
                      <p>{msg.text}</p>
                    </div>
                  )}

                  {hasProducts && (
                    <section className="products-panel">
                      <div className="products-panel-header">
                        <div>
                          <p className="eyebrow">Product options</p>
                          <h3>Recommended for you</h3>
                        </div>

                        <span>
                          {msg.products.length} item
                          {msg.products.length === 1 ? "" : "s"}
                        </span>
                      </div>

                      <div className="products-grid separated-products-grid">
                        {msg.products.map((product, pIndex) => {
                          const productKey = getProductKey(product, pIndex);
                          const imageUrl = getProductImage(product);
                          const showImage =
                            imageUrl && !failedImages[productKey];

                          return (
                            <article className="product-card" key={productKey}>
                              <div className="product-image">
                                {showImage ? (
                                  <img
                                    src={imageUrl}
                                    alt={product.name || "Kapruka product"}
                                    title={product.name || "Kapruka product"}
                                    onError={() => {
                                      setFailedImages((prev) => ({
                                        ...prev,
                                        [productKey]: true,
                                      }));
                                    }}
                                  />
                                ) : (
                                  <span>🛍️</span>
                                )}
                              </div>

                              <div className="product-body">
                                <h3 title={product.name}>{product.name}</h3>

                                <p className="price">
                                  {formatPrice(product.price)}
                                </p>

                                {product.why && (
                                  <p className="why">{product.why}</p>
                                )}

                                <div className="product-actions">
                                  {product.url && (
                                    <a
                                      href={product.url}
                                      target="_blank"
                                      rel="noreferrer"
                                    >
                                      View
                                    </a>
                                  )}

                                  <button onClick={() => addToCart(product)}>
                                    Add to cart
                                  </button>
                                </div>
                              </div>
                            </article>
                          );
                        })}
                      </div>
                    </section>
                  )}

                  {(hasCheckout || hasQuickReplies) && (
                    <div className="assistant-actions-panel">
                      {hasCheckout && (
                        <a
                          className="checkout-link"
                          href={msg.checkoutUrl}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Continue to Kapruka payment
                        </a>
                      )}

                      {hasQuickReplies && (
                        <div className="quick-replies">
                          {msg.quickReplies.map((reply, rIndex) => (
                            <button
                              key={rIndex}
                              onClick={() => sendMessage(reply)}
                            >
                              {reply}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {loading && (
            <div className="message-row assistant">
              <div className="message-stack assistant">
                <div className="bubble typing">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}

          <div ref={chatEndRef} />
        </div>

        <form
          className="composer"
          onSubmit={(e) => {
            e.preventDefault();
            sendMessage();
          }}
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask for products, gifts, delivery dates, Sinhala/Tanglish help..."
          />

          <button type="submit" disabled={loading}>
            Send
          </button>
        </form>
      </section>

      <aside className="cart-panel">
        <div className="cart-header">
          <div>
            <p className="eyebrow">Multi-item cart</p>
            <h2>Your cart</h2>
          </div>

          <span>{cart.length}</span>
        </div>

        <div className="cart-items">
          {cart.length === 0 ? (
            <p className="empty-cart">
              Add products from the chat. Then the agent can help with delivery
              date, recipient details, and checkout.
            </p>
          ) : (
            cart.map((item, index) => (
              <div className="cart-item" key={`${item.id}-${index}`}>
                <div>
                  <h4>{item.name}</h4>
                  <p>{formatPrice(item.price)}</p>
                </div>

                <button onClick={() => removeFromCart(index)}>×</button>
              </div>
            ))
          )}
        </div>

        <div className="cart-footer">
          <div className="total-row">
            <span>Approx. total</span>
            <strong>
              {cartTotal > 0 ? `Rs. ${cartTotal.toLocaleString()}` : "—"}
            </strong>
          </div>

          <button
            className="checkout-button"
            onClick={checkoutWithAgent}
            disabled={cart.length === 0}
          >
            Checkout with agent
          </button>
        </div>
      </aside>

      {showCheckoutForm && (
        <CheckoutForm
          cart={cart}
          cartTotal={cartTotal}
          onClose={() => setShowCheckoutForm(false)}
          onSubmit={handleCheckoutSubmit}
        />
      )}
    </main>
  );
}

export default App;
