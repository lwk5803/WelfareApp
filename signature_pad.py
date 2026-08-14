"""
signature_pad.py
-----------------
서명 캔버스 컴포넌트입니다. 처음엔 서드파티 라이브러리(streamlit-drawable-canvas)를
썼는데 최신 Streamlit과 호환이 안 됐고, 그다음엔 구버전(v1) 커스텀 컴포넌트 방식으로
직접 만들었는데 이 프로젝트의 Streamlit 버전은 이미 v1을 지원하지 않는 새 버전(Custom
Components v2)이라 그것도 안 먹혔습니다. 이제 v2 방식(`st.components.v2.component`)으로
다시 만든 버전입니다 - 별도 파일 없이 이 파일 하나로 끝나는 "인라인" 컴포넌트입니다.
"""
import streamlit as st

_HTML = """
<div id="sigpad-wrap">
  <canvas id="sigpad-canvas" width="420" height="150"></canvas>
  <button id="sigpad-clear" type="button">서명 지우기</button>
</div>
<style>
  #sigpad-wrap { display: flex; flex-direction: column; gap: 6px; font-family: sans-serif; }
  #sigpad-canvas {
    border: 1px solid #999; border-radius: 4px; background: #fff;
    touch-action: none; width: 100%; max-width: 420px; height: auto; display: block;
  }
  #sigpad-clear {
    padding: 4px 12px; font-size: 13px; border: 1px solid #999; border-radius: 4px;
    background: #f5f5f5; cursor: pointer; width: fit-content;
  }
  #sigpad-clear:active { background: #e0e0e0; }
</style>
"""

# 서명은 화면(JS)에서 그려서 파이썬으로 값만 올려보내면 되고, 파이썬이 그림 내용을
# 다시 화면에 그려줄 필요는 없어서(단방향), data는 안 쓰고 setStateValue만 씁니다.
_JS = """
export default function (component) {
  const { parentElement, setStateValue } = component
  const canvas = parentElement.querySelector("#sigpad-canvas")
  if (!canvas || canvas._sigInit) return
  canvas._sigInit = true

  const ctx = canvas.getContext("2d")
  let drawing = false
  let last = null
  let hasDrawn = false

  function clearCanvas() {
    ctx.fillStyle = "#ffffff"
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.strokeStyle = "#000000"
    ctx.lineWidth = 3
    ctx.lineCap = "round"
    ctx.lineJoin = "round"
    hasDrawn = false
  }
  clearCanvas()

  function pointerPos(e) {
    const rect = canvas.getBoundingClientRect()
    const scaleX = canvas.width / rect.width
    const scaleY = canvas.height / rect.height
    return { x: (e.clientX - rect.left) * scaleX, y: (e.clientY - rect.top) * scaleY }
  }

  canvas.addEventListener("pointerdown", (e) => {
    drawing = true
    last = pointerPos(e)
    canvas.setPointerCapture(e.pointerId)
  })
  canvas.addEventListener("pointermove", (e) => {
    if (!drawing) return
    const p = pointerPos(e)
    ctx.beginPath()
    ctx.moveTo(last.x, last.y)
    ctx.lineTo(p.x, p.y)
    ctx.stroke()
    last = p
    hasDrawn = true
  })
  function endStroke() {
    if (!drawing) return
    drawing = false
    if (hasDrawn) {
      setStateValue("value", canvas.toDataURL("image/png"))
    }
  }
  canvas.addEventListener("pointerup", endStroke)
  canvas.addEventListener("pointercancel", endStroke)
  canvas.addEventListener("pointerleave", endStroke)

  parentElement.querySelector("#sigpad-clear").addEventListener("click", () => {
    clearCanvas()
    setStateValue("value", "")
  })
}
"""

_COMPONENT = st.components.v2.component("welfare_app.signature_pad", html=_HTML, js=_JS)


def signature_pad(key: str) -> str:
    """
    서명 캔버스를 그리고, 서명한 내용을 base64 PNG data URL 문자열로 돌려줍니다.
    (예: "data:image/png;base64,iVBORw0KG...") 아무것도 안 그렸으면 빈 문자열입니다.
    """
    result = _COMPONENT(
        key=key,
        data={},
        default={"value": ""},
        on_value_change=lambda: None,
    )
    return result.value or ""
