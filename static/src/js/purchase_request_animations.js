/** @odoo-module **/

const FORM_SELECTOR = ".o_form_view.ar_purchase_request_form";
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");

function installHeroScene(form) {
    const hero = form.querySelector(".ar_purchase_request_title > div:first-child");
    if (!hero || hero.querySelector(".ar_da_3d_stage")) {
        return;
    }

    const stage = document.createElement("div");
    stage.className = "ar_da_3d_stage";
    stage.setAttribute("aria-hidden", "true");

    const canvas = document.createElement("canvas");
    stage.appendChild(canvas);
    hero.appendChild(stage);

    const context = canvas.getContext("2d", { alpha: true });
    if (!context) {
        stage.remove();
        return;
    }

    let width = 0;
    let height = 0;
    let pixelRatio = 1;
    let pointerX = 0;
    let pointerY = 0;
    let frameId = 0;
    const particles = Array.from({ length: 26 }, (_, index) => ({
        angle: index * 0.74,
        radius: 42 + (index % 7) * 10,
        speed: 0.0016 + (index % 5) * 0.00028,
        y: -28 + (index % 6) * 11,
    }));

    function resize() {
        const rect = stage.getBoundingClientRect();
        width = Math.max(1, rect.width);
        height = Math.max(1, rect.height);
        pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
        canvas.width = Math.round(width * pixelRatio);
        canvas.height = Math.round(height * pixelRatio);
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;
        context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    }

    function project(x, y, z, time) {
        const depth = 540;
        const tiltX = pointerY * 0.26;
        const tiltY = pointerX * 0.34;
        const wave = Math.sin(time * 0.001 + z * 0.018) * 4;
        const rotatedX = x + z * tiltY;
        const rotatedY = y + z * tiltX + wave;
        const scale = depth / (depth + z);
        return {
            x: width * 0.5 + rotatedX * scale,
            y: height * 0.52 + rotatedY * scale,
            scale,
        };
    }

    function roundedRect(x, y, rectWidth, rectHeight, radius) {
        context.beginPath();
        context.moveTo(x + radius, y);
        context.lineTo(x + rectWidth - radius, y);
        context.quadraticCurveTo(x + rectWidth, y, x + rectWidth, y + radius);
        context.lineTo(x + rectWidth, y + rectHeight - radius);
        context.quadraticCurveTo(x + rectWidth, y + rectHeight, x + rectWidth - radius, y + rectHeight);
        context.lineTo(x + radius, y + rectHeight);
        context.quadraticCurveTo(x, y + rectHeight, x, y + rectHeight - radius);
        context.lineTo(x, y + radius);
        context.quadraticCurveTo(x, y, x + radius, y);
    }

    function drawCard(x, y, z, cardWidth, cardHeight, color, time, delay) {
        const point = project(x, y + Math.sin(time * 0.0016 + delay) * 6, z, time);
        const w = cardWidth * point.scale;
        const h = cardHeight * point.scale;
        const radius = 10 * point.scale;

        context.save();
        context.translate(point.x, point.y);
        context.rotate((pointerX * 0.06 + Math.sin(time * 0.001 + delay) * 0.025) * point.scale);
        context.shadowColor = "rgba(15, 23, 42, 0.18)";
        context.shadowBlur = 18 * point.scale;
        context.shadowOffsetY = 12 * point.scale;
        roundedRect(-w / 2, -h / 2, w, h, radius);
        const gradient = context.createLinearGradient(-w / 2, -h / 2, w / 2, h / 2);
        gradient.addColorStop(0, color[0]);
        gradient.addColorStop(1, color[1]);
        context.fillStyle = gradient;
        context.fill();

        context.shadowColor = "transparent";
        context.strokeStyle = "rgba(255, 255, 255, 0.55)";
        context.lineWidth = Math.max(1, 1.1 * point.scale);
        context.stroke();

        context.fillStyle = "rgba(255, 255, 255, 0.72)";
        roundedRect(-w * 0.34, -h * 0.18, w * 0.44, 4 * point.scale, 2 * point.scale);
        context.fill();
        roundedRect(-w * 0.34, h * 0.03, w * 0.66, 4 * point.scale, 2 * point.scale);
        context.fill();
        context.restore();
    }

    function drawCoin(x, y, z, radius, time, delay) {
        const point = project(x, y, z, time);
        const r = radius * point.scale;
        context.save();
        context.translate(point.x, point.y);
        context.rotate(time * 0.0018 + delay);
        context.scale(Math.max(0.2, Math.abs(Math.cos(time * 0.0018 + delay))), 1);
        context.shadowColor = "rgba(180, 83, 9, 0.22)";
        context.shadowBlur = 14 * point.scale;
        context.beginPath();
        context.arc(0, 0, r, 0, Math.PI * 2);
        const gradient = context.createRadialGradient(-r * 0.4, -r * 0.45, r * 0.2, 0, 0, r);
        gradient.addColorStop(0, "#fff7cc");
        gradient.addColorStop(0.48, "#f6c453");
        gradient.addColorStop(1, "#b45309");
        context.fillStyle = gradient;
        context.fill();
        context.shadowColor = "transparent";
        context.strokeStyle = "rgba(255, 255, 255, 0.55)";
        context.lineWidth = Math.max(1, 1.2 * point.scale);
        context.stroke();
        context.restore();
    }

    function render(time) {
        if (!stage.isConnected) {
            window.cancelAnimationFrame(frameId);
            window.removeEventListener("resize", resize);
            return;
        }

        if (width === 0 || height === 0) {
            resize();
        }

        context.clearRect(0, 0, width, height);
        const glow = context.createRadialGradient(width * 0.5, height * 0.55, 8, width * 0.5, height * 0.55, width * 0.5);
        glow.addColorStop(0, "rgba(45, 212, 191, 0.22)");
        glow.addColorStop(0.45, "rgba(37, 99, 235, 0.12)");
        glow.addColorStop(1, "rgba(255, 255, 255, 0)");
        context.fillStyle = glow;
        context.fillRect(0, 0, width, height);

        context.strokeStyle = "rgba(15, 118, 110, 0.11)";
        context.lineWidth = 1;
        for (let i = -3; i <= 3; i += 1) {
            const a = project(i * 34, 48, 120, time);
            const b = project(i * 62, -52, -120, time);
            context.beginPath();
            context.moveTo(a.x, a.y);
            context.lineTo(b.x, b.y);
            context.stroke();
        }

        particles.forEach((particle) => {
            const angle = particle.angle + time * particle.speed;
            const x = Math.cos(angle) * particle.radius;
            const z = Math.sin(angle) * 160;
            const p = project(x, particle.y, z, time);
            context.beginPath();
            context.fillStyle = z > 0 ? "rgba(20, 184, 166, 0.45)" : "rgba(37, 99, 235, 0.25)";
            context.arc(p.x, p.y, Math.max(1.2, 2.8 * p.scale), 0, Math.PI * 2);
            context.fill();
        });

        drawCard(-30, -10, 80, 94, 58, ["rgba(15, 118, 110, 0.94)", "rgba(37, 99, 235, 0.9)"], time, 0.2);
        drawCard(36, 10, -60, 80, 50, ["rgba(255, 255, 255, 0.9)", "rgba(224, 242, 254, 0.92)"], time, 2.2);
        drawCard(12, -30, 10, 70, 44, ["rgba(13, 148, 136, 0.74)", "rgba(59, 130, 246, 0.68)"], time, 4.2);
        drawCoin(78, -34, 18, 14, time, 0.4);
        drawCoin(-76, 30, -28, 11, time, 1.5);

        if (!REDUCED_MOTION.matches) {
            frameId = window.requestAnimationFrame(render);
        }
    }

    hero.addEventListener("pointermove", (event) => {
        const rect = hero.getBoundingClientRect();
        pointerX = ((event.clientX - rect.left) / rect.width - 0.5) * 2;
        pointerY = ((event.clientY - rect.top) / rect.height - 0.5) * -2;
        hero.style.setProperty("--ar-da-tilt-x", `${pointerY * 3}deg`);
        hero.style.setProperty("--ar-da-tilt-y", `${pointerX * -4}deg`);
    });

    hero.addEventListener("pointerleave", () => {
        pointerX = 0;
        pointerY = 0;
        hero.style.setProperty("--ar-da-tilt-x", "0deg");
        hero.style.setProperty("--ar-da-tilt-y", "0deg");
    });

    resize();
    window.addEventListener("resize", resize, { passive: true });
    if (REDUCED_MOTION.matches) {
        render(0);
    } else {
        frameId = window.requestAnimationFrame(render);
    }
}

function animateForm(form) {
    if (!form || form.dataset.arDaAnimated === "1") {
        return;
    }
    form.dataset.arDaAnimated = "1";

    const sheet = form.querySelector(".ar_purchase_request_sheet");
    if (sheet) {
        sheet.classList.add("ar_da_ready");
    }

    installHeroScene(form);

    form.querySelectorAll(".ar_purchase_request_title, .ar_purchase_request_panel").forEach((element) => {
        element.classList.add("ar_da_reveal");
    });

    const amount = form.querySelector(".ar_purchase_request_amount");
    if (!amount) {
        return;
    }

    let lastValue = amount.textContent.trim();
    const observer = new MutationObserver(() => {
        const value = amount.textContent.trim();
        if (value === lastValue) {
            return;
        }
        lastValue = value;
        amount.classList.remove("ar_da_amount_flash");
        window.requestAnimationFrame(() => amount.classList.add("ar_da_amount_flash"));
    });

    observer.observe(amount, {
        childList: true,
        subtree: true,
        characterData: true,
    });
}

function scan() {
    document.querySelectorAll(FORM_SELECTOR).forEach(animateForm);
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", scan);
} else {
    scan();
}

if (document.body) {
    const bodyObserver = new MutationObserver(scan);
    bodyObserver.observe(document.body, {
        childList: true,
        subtree: true,
    });
}
