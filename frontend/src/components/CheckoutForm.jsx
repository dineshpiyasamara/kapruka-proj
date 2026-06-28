import { useMemo, useState } from "react";

function CheckoutForm({ cart, cartTotal, onClose, onSubmit }) {
  const tomorrow = useMemo(() => {
    const date = new Date();
    date.setDate(date.getDate() + 1);
    return date.toISOString().split("T")[0];
  }, []);

  const [formData, setFormData] = useState({
    recipientName: "",
    recipientPhone: "",
    recipientEmail: "",
    deliveryCity: "",
    deliveryAddress: "",
    deliveryDate: tomorrow,
    senderName: "",
    senderPhone: "",
    senderEmail: "",
    giftMessage: "",
    currency: "LKR",
    orderType: "self-shopping",
  });

  const isGiftOrder = formData.orderType === "gift";

  function updateField(field, value) {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
  }

  function updateOrderType(orderType) {
    setFormData((prev) => ({
      ...prev,
      orderType,
    }));
  }

  function handleSubmit(e) {
    e.preventDefault();

    const checkoutPayload = isGiftOrder
      ? {
          ...formData,
          cart,
          cartTotal,
        }
      : {
          ...formData,
          senderName: formData.recipientName,
          senderPhone: formData.recipientPhone,
          senderEmail: formData.recipientEmail,
          giftMessage: "",
          cart,
          cartTotal,
        };

    onSubmit(checkoutPayload);
  }

  return (
    <div className="checkout-overlay">
      <section className="checkout-modal">
        <div className="checkout-modal-header">
          <div>
            <p className="eyebrow">Agent-assisted order</p>
            <h2>Secure checkout flow</h2>
          </div>

          <button className="modal-close-button" onClick={onClose} type="button">
            ×
          </button>
        </div>

        <form className="checkout-form" onSubmit={handleSubmit}>
          <div className="checkout-summary-card">
            <div>
              <p className="summary-label">Items</p>
              <strong>
                {cart.length} item{cart.length === 1 ? "" : "s"}
              </strong>
            </div>

            <div>
              <p className="summary-label">Approx. total</p>
              <strong>
                {cartTotal > 0 ? `Rs. ${cartTotal.toLocaleString()}` : "Pending"}
              </strong>
            </div>
          </div>

          <div className="form-section">
            <h3>Order type</h3>

            <div className="order-type-grid">
              <button
                type="button"
                className={formData.orderType === "self-shopping" ? "active" : ""}
                onClick={() => updateOrderType("self-shopping")}
              >
                🛒 For myself
              </button>

              <button
                type="button"
                className={formData.orderType === "gift" ? "active" : ""}
                onClick={() => updateOrderType("gift")}
              >
                🎁 Sending as a gift
              </button>
            </div>

            <div className="form-grid" style={{ marginTop: "14px" }}>
              <label>
                Currency
                <select
                  value={formData.currency}
                  onChange={(e) => updateField("currency", e.target.value)}
                >
                  <option value="LKR">LKR</option>
                  <option value="USD">USD</option>
                </select>
              </label>
            </div>
          </div>

          <div className="form-section">
            <h3>{isGiftOrder ? "Recipient details" : "Your delivery details"}</h3>

            <div className="form-grid">
              <label>
                {isGiftOrder ? "Recipient name *" : "Your name *"}
                <input
                  required
                  value={formData.recipientName}
                  onChange={(e) => updateField("recipientName", e.target.value)}
                  placeholder={isGiftOrder ? "Ex: Nimal Perera" : "Ex: Your name"}
                />
              </label>

              <label>
                {isGiftOrder ? "Recipient phone *" : "Your phone *"}
                <input
                  required
                  value={formData.recipientPhone}
                  onChange={(e) => updateField("recipientPhone", e.target.value)}
                  placeholder="Ex: 077 123 4567"
                />
              </label>

              <label>
                {isGiftOrder ? "Recipient email" : "Your email"}
                <input
                  value={formData.recipientEmail}
                  onChange={(e) => updateField("recipientEmail", e.target.value)}
                  placeholder="name@example.com (optional)"
                />
              </label>

              <label>
                Delivery city *
                <input
                  required
                  value={formData.deliveryCity}
                  onChange={(e) => updateField("deliveryCity", e.target.value)}
                  placeholder="Ex: Colombo 05, Kandy, Galle"
                />
              </label>
            </div>

            <label>
              Full delivery address *
              <textarea
                required
                value={formData.deliveryAddress}
                onChange={(e) => updateField("deliveryAddress", e.target.value)}
                placeholder="House no, street, area, nearby landmark"
              />
            </label>

            <label>
              Preferred delivery date *
              <input
                required
                type="date"
                min={tomorrow}
                value={formData.deliveryDate}
                onChange={(e) => updateField("deliveryDate", e.target.value)}
              />
            </label>
          </div>

          {isGiftOrder && (
            <>
              <div className="form-section">
                <h3>Sender details</h3>

                <div className="form-grid">
                  <label>
                    Sender name *
                    <input
                      required={isGiftOrder}
                      value={formData.senderName}
                      onChange={(e) => updateField("senderName", e.target.value)}
                      placeholder="Ex: Sanduni Fernando"
                    />
                  </label>

                  <label>
                    Sender phone *
                    <input
                      required={isGiftOrder}
                      value={formData.senderPhone}
                      onChange={(e) => updateField("senderPhone", e.target.value)}
                      placeholder="Ex: 071 234 5678"
                    />
                  </label>

                  <label>
                    Sender email
                    <input
                      value={formData.senderEmail}
                      onChange={(e) => updateField("senderEmail", e.target.value)}
                      placeholder="your@email.com (optional)"
                    />
                  </label>
                </div>
              </div>

              <div className="form-section">
                <h3>Gift message</h3>

                <label>
                  Message card note
                  <textarea
                    value={formData.giftMessage}
                    onChange={(e) => updateField("giftMessage", e.target.value)}
                    placeholder="Ex: Happy birthday Amma! With love..."
                  />
                </label>
              </div>
            </>
          )}

          <div className="checkout-actions">
            <button type="button" className="secondary-button" onClick={onClose}>
              Back to cart
            </button>

            <button type="submit" className="primary-button">
              Check delivery & continue
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

export default CheckoutForm;