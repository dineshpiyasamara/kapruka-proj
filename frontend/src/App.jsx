import { useMemo, useRef, useState } from "react";
import CheckoutForm from "./components/CheckoutForm";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

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

function App() {
  const [sessionId] = useState(makeSessionId);
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text:
        "Ayubowan! I’m your Kapruka shopping buddy. Tell me what you need — groceries, gifts, electronics, flowers, cakes, or even a last-minute rescue mission.",
      products: [],
      quickReplies: starterPrompts.slice(0, 3),
    },
  ]);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [cart, setCart] = useState([]);
  const [showCheckoutForm, setShowCheckoutForm] = useState(false);
  const chatEndRef = useRef(null);

  const cartTotal = useMemo(() => {
    return cart.reduce((sum, item) => {
      const raw = String(item.price || "").replace(/[^\d.]/g, "");
      const value = Number(raw || 0);
      return sum + value;
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
      const res = await fetch(`${API_BASE}/api/chat`, {
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
          text:
            "Aiyo, I could not reach the shopping agent right now. Check whether the backend is running on port 8000.",
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
          `${index + 1}. ${item.name} - ${item.price || "price unknown"}`
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
            <button onClick={() => sendMessage("I want to buy groceries for myself")}>
              🛒 Everyday shopping
            </button>
            <button onClick={() => sendMessage("I need to send a gift to someone")}>
              🎁 Gift mode
            </button>
            <button onClick={() => sendMessage("මට Sinhala වලින් help කරන්න")}>
              🇱🇰 Sinhala
            </button>
            <button onClick={() => sendMessage("Tanglish walin shopping help ekak denna")}>
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
          {messages.map((msg, index) => (
            <div key={index} className={`message-row ${msg.role}`}>
              <div className="bubble">
                <p>{msg.text}</p>

                {msg.products?.length > 0 && (
                  <div className="products-grid">
                    {msg.products.map((product, pIndex) => (
                      <article className="product-card" key={`${product.id}-${pIndex}`}>
                        <div className="product-image">
                          {product.image ? (
                            <img src={product.image} alt={product.name} />
                          ) : (
                            <span>🛍️</span>
                          )}
                        </div>

                        <div className="product-body">
                          <h3>{product.name}</h3>

                          <p className="price">
                            {product.price || "Price available in Kapruka"}
                          </p>

                          {product.why && <p className="why">{product.why}</p>}

                          <div className="product-actions">
                            {product.url && (
                              <a href={product.url} target="_blank" rel="noreferrer">
                                View
                              </a>
                            )}

                            <button onClick={() => addToCart(product)}>
                              Add to cart
                            </button>
                          </div>
                        </div>
                      </article>
                    ))}
                  </div>
                )}

                {msg.checkoutUrl && (
                  <a
                    className="checkout-link"
                    href={msg.checkoutUrl}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Continue to Kapruka payment
                  </a>
                )}

                {msg.quickReplies?.length > 0 && (
                  <div className="quick-replies">
                    {msg.quickReplies.map((reply, rIndex) => (
                      <button key={rIndex} onClick={() => sendMessage(reply)}>
                        {reply}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="message-row assistant">
              <div className="bubble typing">
                <span></span>
                <span></span>
                <span></span>
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
                  <p>{item.price || "Price pending"}</p>
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
