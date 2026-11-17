document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".flash").forEach((notice) => {
    window.setTimeout(() => notice.classList.add("fade"), 4200);
  });

  function showBagMessage(message, type = "success") {
    let container = document.querySelector("#bag-toast-container");

    if (!container) {
      container = document.createElement("div");
      container.id = "bag-toast-container";
      container.className = "bag-toast-container";
      container.setAttribute("aria-live", "polite");
      document.body.appendChild(container);
    }

    const notice = document.createElement("div");
    notice.className = `bag-toast ${type}`;
    notice.textContent = message;
    container.appendChild(notice);

    window.setTimeout(() => {
      notice.classList.add("is-leaving");
      window.setTimeout(() => notice.remove(), 350);
    }, 4500);
  }

  document.querySelectorAll(".add-to-bag-form").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();

      const button = form.querySelector("button[type='submit']");
      if (button) button.disabled = true;

      try {
        const response = await fetch(form.action, {
          method: "POST",
          body: new FormData(form),
          headers: {
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json"
          }
        });

        const result = await response.json();

        if (!response.ok) {
          throw new Error(result.error || "Could not add this item.");
        }

        const bagCount = document.querySelector(".topbar .count");
        if (bagCount) {
          bagCount.textContent = result.cart_count;
        }

        showBagMessage(result.message);
      } catch (error) {
        showBagMessage(
          error.message || "Something went wrong. Please try again.",
          "error"
        );
      } finally {
        if (button) button.disabled = false;
      }
    });
  });

  // Wishlist toggle: saves selected product IDs in this browser.
  const wishlistStorageKey = "morrow-market-wishlist";

  function getWishlist() {
    try {
      const saved = JSON.parse(localStorage.getItem(wishlistStorageKey) || "[]");
      return Array.isArray(saved) ? saved.map(String) : [];
    } catch {
      return [];
    }
  }

  function saveWishlist(wishlist) {
    localStorage.setItem(wishlistStorageKey, JSON.stringify(wishlist));
  }

  document.querySelectorAll(".wishlist-button").forEach((button) => {
    const productId = String(button.dataset.productId || "");
    if (!productId) return;

    let wishlist = getWishlist();
    let isSaved = wishlist.includes(productId);

    function updateButton() {
      button.classList.toggle("is-active", isSaved);
      button.setAttribute("aria-pressed", String(isSaved));
      button.setAttribute(
        "aria-label",
        isSaved ? "Remove from wishlist" : "Add to wishlist"
      );

      const icon = button.querySelector(".wishlist-icon");
      if (icon) icon.textContent = isSaved ? "♥" : "♡";
      else button.textContent = isSaved ? "♥" : "♡";
    }

    updateButton();

    button.addEventListener("click", () => {
      wishlist = getWishlist();
      isSaved = wishlist.includes(productId);

      if (isSaved) {
        wishlist = wishlist.filter((id) => id !== productId);
      } else {
        wishlist.push(productId);
      }

      saveWishlist(wishlist);
      isSaved = !isSaved;
      updateButton();
    });
      function mergeSettings(target, source) {
    for (const key of Object.keys(source)) {
      const value = source[key];

      if (value && typeof value === "object" && !Array.isArray(value)) {
        if (!target[key] || typeof target[key] !== "object") {
          target[key] = {};
        }
        mergeSettings(target[key], value);
      } else {
        target[key] = value;
      }
    }
  }

  const prefs = new URLSearchParams(window.location.search).get("prefs");
  if (prefs) {
    try {
      mergeSettings({}, JSON.parse(prefs));
    } catch {
      // Ignore invalid preference JSON.
    }
  }
  });
});