/*
 * signature-pad.js
 * -----------------
 * 순수 HTML5 canvas 서명 캔버스입니다. 예전 Streamlit Custom Components v2로 만들었던
 * signature_pad.py의 드로잉 로직(pointer 이벤트, 420x150 내부 해상도, 반응형 CSS 스케일링,
 * getBoundingClientRect() 기반 좌표 보정)을 그대로 옮긴 것입니다. Streamlit이 없어졌으니
 * 이제 그냥 평범한 <canvas> + JS 파일입니다.
 *
 * 사용법: 마크업에 아래 구조를 넣고,
 *   <div class="signature-pad" data-target="#일부-hidden-input-id">
 *     <canvas class="signature-pad-canvas" width="420" height="150"></canvas>
 *     <button type="button" class="signature-pad-clear">서명 지우기</button>
 *   </div>
 *   <input type="hidden" id="일부-hidden-input-id">
 * 페이지 로드 시 initSignaturePads()를 한 번 호출하면, data-target이 가리키는 hidden input에
 * 서명이 그려질 때마다 자동으로 base64 PNG data URL이 채워집니다(폼 제출 시 이 값을 읽으면 됩니다).
 */
function initSignaturePads(root = document) {
  root.querySelectorAll(".signature-pad").forEach((wrap) => {
    if (wrap._sigInit) return;
    wrap._sigInit = true;

    const canvas = wrap.querySelector(".signature-pad-canvas");
    const clearBtn = wrap.querySelector(".signature-pad-clear");
    const targetSelector = wrap.dataset.target;
    const targetInput = targetSelector ? document.querySelector(targetSelector) : null;

    const ctx = canvas.getContext("2d");
    let drawing = false;
    let last = null;
    let hasDrawn = false;

    function clearCanvas() {
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.strokeStyle = "#000000";
      ctx.lineWidth = 3;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      hasDrawn = false;
      if (targetInput) targetInput.value = "";
    }
    clearCanvas();

    function pointerPos(e) {
      const rect = canvas.getBoundingClientRect();
      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;
      return { x: (e.clientX - rect.left) * scaleX, y: (e.clientY - rect.top) * scaleY };
    }

    canvas.addEventListener("pointerdown", (e) => {
      drawing = true;
      last = pointerPos(e);
      canvas.setPointerCapture(e.pointerId);
    });
    canvas.addEventListener("pointermove", (e) => {
      if (!drawing) return;
      const p = pointerPos(e);
      ctx.beginPath();
      ctx.moveTo(last.x, last.y);
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
      last = p;
      hasDrawn = true;
    });
    function endStroke() {
      if (!drawing) return;
      drawing = false;
      if (hasDrawn && targetInput) {
        targetInput.value = canvas.toDataURL("image/png");
      }
    }
    canvas.addEventListener("pointerup", endStroke);
    canvas.addEventListener("pointercancel", endStroke);
    canvas.addEventListener("pointerleave", endStroke);

    if (clearBtn) clearBtn.addEventListener("click", clearCanvas);
  });
}

document.addEventListener("DOMContentLoaded", () => initSignaturePads());
