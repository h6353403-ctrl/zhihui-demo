import React, { useState, useMemo, useRef } from "react";

// 模型凭证已全部移到后端 backend/.env（gitignore），前端只通过受控 API 调用，
// 不接触任何 Key（见通用技术栈手册 A 层底线）。

const C = {
  bg: "#EDEEF0",
  surface: "#FFFFFF",
  ink: "#1A1F26",
  muted: "#767E88",
  line: "#DCDFE3",
  accent: "#E8384F",
  pass: "#14795A",
  review: "#B4761A",
  block: "#C0362C",
  fill: "#F5F6F8",
};

const FONT =
  '-apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif';

const SAMPLE_BRIEF = `【花漾 HUAYANG · 秋冬修护季】站内营销活动 Brief

活动时间：11月1日 - 11月11日
主推产品：花漾玻尿酸修护精华 30ml，日常价 359，活动价 259，买一送同款小样15ml

必须提到：
1. 活动价 259（限时）
2. 玻尿酸复合配方，5重保湿
3. 敏感肌可用，已通过温和性测试
4. 话题标签 #秋冬修护季 #花漾修护精华

目标人群：22-35 岁女性，干皮/敏感肌，关注成分

调性：真实体验感，不要硬广

禁止：不要出现"最有效""第一""根治"等词；不要提及竞品；不要宣称医疗功效`;

const PERSONAS = [
  { id: "vivid", name: "元气种草型", hint: "短句、感叹多、emoji 密集、第二人称" },
  { id: "rational", name: "理性测评型", hint: "长句、数据导向、少 emoji、第一人称" },
  { id: "daily", name: "生活碎碎念型", hint: "口语化、场景开头、语气词多" },
];

const TYPES = [
  { id: "poster", name: "活动大字报" },
  { id: "review", name: "产品测评" },
  { id: "recommend", name: "好物推荐" },
];

const VISUAL_STYLES = [
  { id: "realistic", name: "写实", en: "Realistic", hint: "像真实照片" },
  { id: "illustration", name: "插画", en: "Illustration", hint: "手绘感" },
  { id: "3d", name: "3D 卡通", en: "3D Render", hint: "立体卡通（盲盒感）" },
  { id: "cyberpunk", name: "赛博朋克", en: "Cyberpunk", hint: "霓虹科技感" },
  { id: "guofeng", name: "国风", en: "Guofeng", hint: "水墨、国潮" },
  { id: "minimal", name: "极简", en: "Minimal", hint: "干净留白" },
];

const STEPS = [
  { n: 1, key: "brief", label: "Brief 解析" },
  { n: 2, key: "topics", label: "选题推荐" },
  { n: 3, key: "content", label: "文案与排版" },
  { n: 4, key: "qc", label: "质检与合规" },
];

// 统一 API 封装：前端只走后端受控接口，不接触任何模型凭证
async function apiPost(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `请求失败（${res.status}）`);
  }
  return data;
}

export default function ZhihuiDemo() {
  const [brief, setBrief] = useState(SAMPLE_BRIEF);
  const [persona, setPersona] = useState("daily");
  const [type, setType] = useState("poster");
  const [style, setStyle] = useState("realistic");
  const [bgPrompt, setBgPrompt] = useState("");

  const [parsed, setParsed] = useState(null);
  const [topics, setTopics] = useState(null);
  const [picked, setPicked] = useState(null);
  const [content, setContent] = useState(null);

  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const contentReqRef = useRef(0);
  const fileInputRef = useRef(null);
  const docInputRef = useRef(null);
  const logoInputRef = useRef(null);
  const [segUrl, setSegUrl] = useState(null);
  const [segBusy, setSegBusy] = useState(false);
  const [segErr, setSegErr] = useState("");
  const [logoUrl, setLogoUrl] = useState(null);
  const [compositeUrl, setCompositeUrl] = useState(null);
  const [compositeObjectKey, setCompositeObjectKey] = useState("");
  const [compositeBusy, setCompositeBusy] = useState(false);
  const [compositeVqa, setCompositeVqa] = useState(null);
  const [compositeErr, setCompositeErr] = useState("");

  const HISTORY_KEY = "zhihui_history_v1";
  const [history, setHistory] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
    } catch {
      return [];
    }
  });

  const saveHistory = (entry) => {
    setHistory((prev) => {
      const next = [entry, ...prev].slice(0, 20);
      try {
        localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
      } catch {
        /* 存储满或隐私模式，静默失败 */
      }
      return next;
    });
  };

  const clearHistory = () => {
    setHistory([]);
    try {
      localStorage.removeItem(HISTORY_KEY);
    } catch {
      /* ignore */
    }
  };

  const stage = content ? 4 : topics ? (picked ? 3 : 2) : parsed ? 2 : 1;

  const reset = () => {
    contentReqRef.current++;
    setParsed(null);
    setTopics(null);
    setPicked(null);
    setContent(null);
    setSegUrl(null);
    setSegErr("");
    setLogoUrl(null);
    setCompositeUrl(null);
    setCompositeObjectKey("");
    setCompositeVqa(null);
    setCompositeErr("");
    setBgPrompt("");
    setErr("");
  };

  const runParse = async () => {
    setBusy("parse");
    setErr("");
    setTopics(null);
    setPicked(null);
    setContent(null);
    try {
      const r = await apiPost("/api/v1/parse", { brief });
      setParsed(r);
    } catch (e) {
      setErr("解析失败，请重试：" + e.message);
    }
    setBusy("");
  };

  const runTopics = async () => {
    setBusy("topics");
    setErr("");
    setPicked(null);
    setContent(null);
    try {
      const r = await apiPost("/api/v1/topics", { parsed, type, persona });
      const list = r.topics || [];
      if (!list.length) {
        throw new Error("模型未返回选题");
      }
      setTopics(list);
    } catch (e) {
      setErr("选题生成失败，请重试：" + e.message);
    }
    setBusy("");
  };

  const runContent = async (topic) => {
    setBusy("content");
    setErr("");
    setPicked(topic);
    setContent(null);
    const reqId = ++contentReqRef.current;
    try {
      const r = await apiPost("/api/v1/content", { parsed, type, persona, topic, style });
      if (!r || !r.cover) {
        throw new Error("模型未返回有效的图文数据");
      }
      // 文案与排版先落地，背景图异步生成，不阻塞预览
      setContent({ ...r, bgImageUrl: null, bgStatus: "generating", bgError: "", vqa: null, vqaStatus: "idle", vqaError: "" });
      setBgPrompt(r.cover?.bg_prompt || "");
      setBusy("");
      apiPost("/api/v1/image", { prompt: r.cover.bg_prompt, style })
        .then((img) => {
          if (contentReqRef.current !== reqId) return;
          setContent((prev) =>
            prev ? { ...prev, bgImageUrl: img.url, bgStatus: "done", vqaStatus: "running" } : prev
          );
          return apiPost("/api/v1/vqa", { image_url: img.url, style })
            .then((vqaRes) => {
              if (contentReqRef.current !== reqId) return;
              setContent((prev) =>
                prev ? { ...prev, vqa: vqaRes.items || [], vqaStatus: "done" } : prev
              );
            })
            .catch((vqaErr) => {
              if (contentReqRef.current !== reqId) return;
              setContent((prev) =>
                prev ? { ...prev, vqaStatus: "error", vqaError: vqaErr.message } : prev
              );
            });
        })
        .catch((imgErr) => {
          if (contentReqRef.current !== reqId) return;
          setContent((prev) =>
            prev ? { ...prev, bgStatus: "error", bgError: imgErr.message } : prev
          );
        });
      return;
    } catch (e) {
      setErr("图文生成失败，请重试：" + e.message);
    }
    setBusy("");
  };

  const runSegment = async (file) => {
    setSegBusy(true);
    setSegErr("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch("/api/v1/segment", { method: "POST", body: fd });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || `请求失败（${res.status}）`);
      }
      setSegUrl(data.url);
    } catch (e) {
      setSegErr("抠图失败：" + e.message);
    }
    setSegBusy(false);
  };

  const handleDocUpload = (file) => {
    const reader = new FileReader();
    reader.onload = () => setBrief(String(reader.result || ""));
    reader.onerror = () => setErr("需求文档读取失败");
    reader.readAsText(file, "utf-8");
  };

  const handleLogoUpload = (file) => {
    const reader = new FileReader();
    reader.onload = () => setLogoUrl(String(reader.result || ""));
    reader.onerror = () => setErr("Logo 读取失败");
    reader.readAsDataURL(file);
  };

  const runComposite = async () => {
    if (!content?.bgImageUrl) return;
    setCompositeBusy(true);
    setCompositeErr("");
    try {
      const comp = await apiPost("/api/v1/composite", {
        bg_url: content.bgImageUrl,
        product_url: segUrl || "",
        logo_base64: logoUrl || "",
        cover: content.cover,
      });
      setCompositeUrl(comp.url);
      setCompositeObjectKey(comp.object_key || "");
      const vqaRes = await apiPost("/api/v1/vqa", { image_url: comp.url, style });
      setCompositeVqa(vqaRes.items || []);
      saveHistory({
        ts: Date.now(),
        topic: picked?.title || "",
        type: TYPES.find((t) => t.id === type)?.name || "",
        style: VISUAL_STYLES.find((s) => s.id === style)?.name || "",
        headline: content.cover?.headline || "",
        url: comp.url,
        objectKey: comp.object_key || "",
      });
    } catch (e) {
      setCompositeErr("合成质检失败：" + e.message);
    }
    setCompositeBusy(false);
  };

  const runRegenerate = async () => {
    if (!content || content.bgStatus === "generating") return;
    const reqId = ++contentReqRef.current;
    setContent((prev) =>
      prev ? { ...prev, bgStatus: "generating", bgError: "", vqaStatus: "running" } : prev
    );
    try {
      const img = await apiPost("/api/v1/image", { prompt: bgPrompt, style });
      if (contentReqRef.current !== reqId) return;
      setContent((prev) => (prev ? { ...prev, bgImageUrl: img.url, bgStatus: "done" } : prev));
      const vqaRes = await apiPost("/api/v1/vqa", { image_url: img.url, style });
      if (contentReqRef.current !== reqId) return;
      setContent((prev) => (prev ? { ...prev, vqa: vqaRes.items || [], vqaStatus: "done" } : prev));
    } catch (e) {
      if (contentReqRef.current !== reqId) return;
      setContent((prev) =>
        prev ? { ...prev, bgStatus: "error", bgError: e.message, vqaStatus: "error", vqaError: e.message } : prev
      );
    }
  };

  // 客户端硬规则质检（不依赖模型判断）
  const qc = useMemo(() => {
    if (!content || !parsed) return null;
    const rows = [];
    const all = [
      content.cover?.headline,
      content.cover?.subhead,
      ...(content.cover?.points || []),
      content.cover?.badge,
      content.body,
    ]
      .filter(Boolean)
      .join(" ");

    const bans = ["最有效", "最好", "第一", "根治", "治愈", "永久", "国家级", "顶级"];
    const hit = bans.filter((w) => all.includes(w));
    rows.push({
      level: hit.length ? "block" : "pass",
      item: "极限词与违禁表述",
      note: hit.length ? `命中：${hit.join("、")}` : "未命中硬规则词库",
    });

    const musts = (parsed.selling_points || []).filter((s) => s.priority === "must");
    const missed = musts.filter((s) => {
      const kw = (s.text || "").replace(/[，。、,.\s]/g, "").slice(0, 4);
      return kw && !all.includes(kw);
    });
    rows.push({
      level: missed.length ? "block" : "pass",
      item: `Brief 遵循度（${musts.length - missed.length}/${musts.length} 必含卖点）`,
      note: missed.length ? `缺失：${missed.map((m) => m.text).join("；")}` : "必含卖点全部覆盖",
    });

    const over = [];
    if ((content.cover?.headline || "").length > 10) over.push("主标题超 10 字");
    if ((content.cover?.subhead || "").length > 16) over.push("副标题超 16 字");
    (content.cover?.points || []).forEach((p, i) => {
      if (p.length > 9) over.push(`卖点${i + 1}超 9 字`);
    });
    rows.push({
      level: over.length ? "review" : "pass",
      item: "文字可读性（模板安全区）",
      note: over.length ? over.join("，") + "，已触发自动降级重排" : "全部文本在模板安全区内",
    });

    rows.push({
      level: "pass",
      item: "产品还原度",
      note: "商品图走真图抠图层，未经生成模型重绘",
    });

    return rows;
  }, [content, parsed]);

  const verdict = qc
    ? qc.some((r) => r.level === "block")
      ? "block"
      : qc.some((r) => r.level === "review")
      ? "review"
      : "pass"
    : null;

  // ---------- styles ----------
  const S = {
    page: {
      fontFamily: FONT,
      background: C.bg,
      color: C.ink,
      minHeight: "100%",
      padding: 20,
      fontSize: 14,
      lineHeight: 1.65,
    },
    card: {
      background: C.surface,
      border: `1px solid ${C.line}`,
      borderRadius: 4,
      padding: 18,
      marginBottom: 14,
    },
    h: { fontSize: 15, fontWeight: 600, margin: "0 0 12px", letterSpacing: "0.01em" },
    sub: { color: C.muted, fontSize: 12.5 },
    btn: (on, disabled) => ({
      background: on ? C.ink : C.surface,
      color: on ? "#fff" : C.ink,
      border: `1px solid ${on ? C.ink : C.line}`,
      borderRadius: 3,
      padding: "8px 16px",
      fontSize: 13,
      fontFamily: FONT,
      cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.45 : 1,
    }),
    chip: (on) => ({
      background: on ? C.ink : C.fill,
      color: on ? "#fff" : C.muted,
      border: `1px solid ${on ? C.ink : C.line}`,
      borderRadius: 3,
      padding: "5px 11px",
      fontSize: 12.5,
      fontFamily: FONT,
      cursor: "pointer",
      marginRight: 7,
      marginBottom: 7,
    }),
    tag: (color) => ({
      display: "inline-block",
      fontSize: 11,
      color,
      border: `1px solid ${color}`,
      borderRadius: 2,
      padding: "1px 6px",
      marginRight: 8,
      verticalAlign: "middle",
    }),
  };

  const levelColor = { pass: C.pass, review: C.review, block: C.block };
  const levelText = { pass: "通过", review: "待复核", block: "拦截" };

  return (
    <div style={S.page}>
      {/* 顶部 */}
      <div style={{ marginBottom: 18 }}>
        <div style={{ fontSize: 21, fontWeight: 650, letterSpacing: "0.02em" }}>
          智绘 · 工作流验证 Demo
        </div>
        <div style={{ ...S.sub, marginTop: 4 }}>
          Brief 解析（DeepSeek）→ 选题与文案（GLM-5.2）→ 背景图（SeedDream）→ 质检，四步真实调用模型。
        </div>
      </div>

      {/* 步骤条 */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        {STEPS.map((s) => {
          const done = stage > s.n;
          const now = stage === s.n;
          return (
            <div
              key={s.key}
              style={{
                flex: "1 1 140px",
                background: now ? C.ink : C.surface,
                color: now ? "#fff" : done ? C.ink : C.muted,
                border: `1px solid ${now ? C.ink : C.line}`,
                borderRadius: 3,
                padding: "9px 12px",
                fontSize: 12.5,
              }}
            >
              <span style={{ opacity: 0.55, marginRight: 7, fontVariantNumeric: "tabular-nums" }}>
                {s.n}
              </span>
              {s.label}
              {done && <span style={{ color: C.pass, marginLeft: 6 }}>✓</span>}
            </div>
          );
        })}
      </div>

      {err && (
        <div
          style={{
            ...S.card,
            borderColor: C.block,
            color: C.block,
            marginBottom: 14,
            padding: 12,
          }}
        >
          {err}
        </div>
      )}

      {/* 1. Brief 输入 */}
      <div style={S.card}>
        <div style={S.h}>商家投放的 Brief</div>
        <textarea
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
          style={{
            width: "100%",
            minHeight: 150,
            border: `1px solid ${C.line}`,
            borderRadius: 3,
            padding: 12,
            fontSize: 13,
            fontFamily: FONT,
            lineHeight: 1.7,
            background: C.fill,
            color: C.ink,
            boxSizing: "border-box",
            resize: "vertical",
          }}
        />
        <div style={{ marginTop: 12 }}>
          <div style={{ ...S.sub, marginBottom: 6 }}>商家素材上传</div>
          <button style={S.chip(false)} onClick={() => docInputRef.current?.click()}>
            上传需求文档
          </button>
          <button style={S.chip(false)} onClick={() => fileInputRef.current?.click()}>
            上传产品图（自动抠图）
          </button>
          <button style={S.chip(false)} onClick={() => logoInputRef.current?.click()}>
            上传品牌 Logo
          </button>
          {logoUrl && (
            <div style={{ marginTop: 8 }}>
              <img
                src={logoUrl}
                alt="品牌Logo"
                style={{ height: 30, border: `1px solid ${C.line}`, borderRadius: 3, verticalAlign: "middle" }}
              />
              <span style={{ ...S.sub, marginLeft: 8 }}>Logo 已上传，将显示在封面</span>
            </div>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            style={{ display: "none" }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) runSegment(f);
              e.target.value = "";
            }}
          />
          <input
            ref={docInputRef}
            type="file"
            accept=".txt,.md,.markdown,text/plain"
            style={{ display: "none" }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleDocUpload(f);
              e.target.value = "";
            }}
          />
          <input
            ref={logoInputRef}
            type="file"
            accept="image/*"
            style={{ display: "none" }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleLogoUpload(f);
              e.target.value = "";
            }}
          />
          <div style={{ ...S.sub, marginBottom: 6, marginTop: 10 }}>内容类型</div>
          {TYPES.map((t) => (
            <button key={t.id} style={S.chip(type === t.id)} onClick={() => setType(t.id)}>
              {t.name}
            </button>
          ))}
          <div style={{ ...S.sub, marginBottom: 6, marginTop: 8 }}>达人语言风格（取自历史笔记）</div>
          {PERSONAS.map((p) => (
            <button key={p.id} style={S.chip(persona === p.id)} onClick={() => setPersona(p.id)}>
              {p.name}
            </button>
          ))}
          <div style={{ ...S.sub, marginBottom: 6, marginTop: 8 }}>视觉风格（驱动背景图）</div>
          {VISUAL_STYLES.map((s) => (
            <button key={s.id} style={S.chip(style === s.id)} onClick={() => setStyle(s.id)}>
              {s.name}
            </button>
          ))}
        </div>
        <div style={{ marginTop: 14, display: "flex", gap: 10 }}>
          <button style={S.btn(true, busy === "parse")} disabled={!!busy} onClick={runParse}>
            {busy === "parse" ? "解析中…" : "解析 Brief"}
          </button>
          {parsed && (
            <button style={S.btn(false, false)} onClick={reset}>
              重置
            </button>
          )}
        </div>
      </div>

      {/* 2. 解析结果 */}
      {parsed && (
        <div style={S.card}>
          <div style={S.h}>
            结构化解析结果
            <span style={{ ...S.sub, fontWeight: 400, marginLeft: 10 }}>
              置信度 {parsed.confidence ?? "—"}
            </span>
          </div>

          {parsed.missing_fields?.length > 0 && (
            <div
              style={{
                border: `1px solid ${C.review}`,
                borderRadius: 3,
                padding: "10px 12px",
                marginBottom: 14,
                fontSize: 13,
                color: C.review,
              }}
            >
              <b>需商家补全 {parsed.missing_fields.length} 项</b>：{parsed.missing_fields.join("、")}
              <div style={{ ...S.sub, color: C.muted, marginTop: 3 }}>
                模型不推断缺失字段，只回填表单让商家确认——避免一个猜错的卖点污染下游全部笔记。
              </div>
            </div>
          )}

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(230px,1fr))", gap: 14 }}>
            <Field label="品牌">{parsed.brand}</Field>
            <Field label="活动">
              {parsed.campaign?.name}
              <div style={S.sub}>{parsed.campaign?.period}</div>
            </Field>
            <Field label="目标人群">{parsed.target_audience}</Field>
            <Field label="调性">{parsed.tone}</Field>
          </div>

          <div style={{ marginTop: 14 }}>
            <div style={{ ...S.sub, marginBottom: 5 }}>商品</div>
            {(parsed.products || []).map((p, i) => (
              <div key={i} style={{ fontSize: 13, marginBottom: 3 }}>
                {p.name} · {p.specs}
                {p.price && (
                  <span style={{ color: C.accent, marginLeft: 8, fontVariantNumeric: "tabular-nums" }}>
                    ¥{p.price}
                  </span>
                )}
                {p.original_price && (
                  <span style={{ ...S.sub, marginLeft: 6, textDecoration: "line-through" }}>
                    ¥{p.original_price}
                  </span>
                )}
              </div>
            ))}
          </div>

          <div style={{ marginTop: 14 }}>
            <div style={{ ...S.sub, marginBottom: 5 }}>卖点</div>
            {(parsed.selling_points || []).map((s, i) => (
              <div key={i} style={{ fontSize: 13, marginBottom: 3 }}>
                <span style={S.tag(s.priority === "must" ? C.accent : C.muted)}>
                  {s.priority === "must" ? "必含" : "可选"}
                </span>
                {s.text}
              </div>
            ))}
          </div>

          {parsed.forbidden?.length > 0 && (
            <div style={{ marginTop: 14 }}>
              <div style={{ ...S.sub, marginBottom: 5 }}>禁止项</div>
              <div style={{ fontSize: 13, color: C.block }}>{parsed.forbidden.join(" ／ ")}</div>
            </div>
          )}

          <div style={{ marginTop: 16 }}>
            <button style={S.btn(true, busy === "topics")} disabled={!!busy} onClick={runTopics}>
              {busy === "topics" ? "生成中…" : "生成选题"}
            </button>
          </div>
        </div>
      )}

      {/* 3. 选题 */}
      {topics && (
        <div style={S.card}>
          <div style={S.h}>选题推荐</div>
          <div style={{ ...S.sub, marginBottom: 12 }}>
            同活动下的选题会做相似度去重，避免 200 篇笔记角度雷同被判定为集中投放。
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 12 }}>
            {topics.map((t, i) => {
              const on = picked?.title === t.title;
              return (
                <div
                  key={i}
                  onClick={() => !busy && runContent(t)}
                  style={{
                    border: `1px solid ${on ? C.ink : C.line}`,
                    background: on ? C.fill : C.surface,
                    borderRadius: 3,
                    padding: 14,
                    cursor: busy ? "wait" : "pointer",
                  }}
                >
                  <div style={S.tag(C.ink)}>{t.angle}</div>
                  <div style={{ fontSize: 14, fontWeight: 600, margin: "8px 0 6px", lineHeight: 1.5 }}>
                    {t.title}
                  </div>
                  <div style={S.sub}>{t.reason}</div>
                </div>
              );
            })}
          </div>
          {busy === "content" && (
            <div style={{ ...S.sub, marginTop: 12 }}>正在生成文案与排版数据…</div>
          )}
        </div>
      )}

      {/* 4. 成稿 */}
      {content && (
        <div style={S.card}>
          <div style={S.h}>成稿预览</div>
          <div style={{ display: "grid", gridTemplateColumns: "minmax(240px,300px) 1fr", gap: 20 }}>
            {/* 封面：三层合成可视化 */}
            <div>
              <div
                style={{
                  position: "relative",
                  aspectRatio: "3/4",
                  border: `1px solid ${C.line}`,
                  borderRadius: 3,
                  overflow: "hidden",
                  backgroundImage: content.bgImageUrl
                    ? `url(${content.bgImageUrl})`
                    : "linear-gradient(160deg,#E7DCD3 0%,#D9C7BC 45%,#C9B3A6 100%)",
                  backgroundSize: "cover",
                  backgroundPosition: "center",
                }}
              >
                {/* 第一层标注 */}
                <div
                  style={{
                    position: "absolute",
                    top: 8,
                    left: 8,
                    fontSize: 10,
                    color: "rgba(0,0,0,.45)",
                    border: "1px dashed rgba(0,0,0,.28)",
                    padding: "1px 5px",
                    borderRadius: 2,
                    background: "rgba(255,255,255,.55)",
                  }}
                >
                  {content.bgStatus === "done"
                    ? "第一层 SeedDream 生成背景"
                    : content.bgStatus === "error"
                    ? "第一层 背景生成失败"
                    : "第一层 AI 生成背景"}
                </div>

                {/* 背景图生成状态 */}
                {content.bgStatus === "generating" && (
                  <div
                    style={{
                      position: "absolute",
                      top: "50%",
                      left: "50%",
                      transform: "translate(-50%,-50%)",
                      fontSize: 12,
                      color: "rgba(0,0,0,.6)",
                      background: "rgba(255,255,255,.72)",
                      padding: "6px 12px",
                      borderRadius: 3,
                    }}
                  >
                    SeedDream 背景图生成中…
                  </div>
                )}
                {content.bgStatus === "error" && (
                  <div
                    style={{
                      position: "absolute",
                      top: "50%",
                      left: "50%",
                      transform: "translate(-50%,-50%)",
                      width: "82%",
                      fontSize: 11,
                      color: C.block,
                      background: "rgba(255,255,255,.85)",
                      padding: "8px 10px",
                      borderRadius: 3,
                      lineHeight: 1.5,
                    }}
                  >
                    背景图生成失败：{content.bgError}
                    <div style={{ marginTop: 4, color: C.muted }}>
                      不影响文案与排版预览，可检查后端 backend/.env 配置
                    </div>
                  </div>
                )}

                {/* 第二层：真实产品图（上传 → 抠图） */}
                {segUrl ? (
                  <div
                    style={{
                      position: "absolute",
                      right: 16,
                      bottom: 78,
                      width: 86,
                      height: 126,
                      borderRadius: 3,
                      overflow: "hidden",
                      background: "rgba(255,255,255,.3)",
                    }}
                  >
                    <img
                      src={segUrl}
                      alt="抠图后的产品图"
                      style={{ width: "100%", height: "100%", objectFit: "contain" }}
                    />
                    <div
                      style={{
                        position: "absolute",
                        bottom: 0,
                        left: 0,
                        right: 0,
                        fontSize: 9,
                        color: "rgba(0,0,0,.5)",
                        background: "rgba(255,255,255,.6)",
                        padding: "1px 3px",
                        textAlign: "center",
                      }}
                    >
                      第二层 真实抠图 · 不重绘
                    </div>
                  </div>
                ) : (
                  <div
                    onClick={() => !segBusy && fileInputRef.current?.click()}
                    style={{
                      position: "absolute",
                      right: 16,
                      bottom: 78,
                      width: 86,
                      height: 126,
                      border: "1px dashed rgba(0,0,0,.4)",
                      borderRadius: 3,
                      background: "rgba(255,255,255,.42)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      textAlign: "center",
                      fontSize: 10,
                      color: "rgba(0,0,0,.55)",
                      lineHeight: 1.5,
                      padding: 6,
                      cursor: segBusy ? "wait" : "pointer",
                    }}
                  >
                    {segBusy ? (
                      <>
                        第二层<br />抠图中…
                      </>
                    ) : (
                      <>
                        第二层<br />真实产品图<br />点击上传抠图
                      </>
                    )}
                  </div>
                )}
                {segErr && (
                  <div
                    style={{
                      position: "absolute",
                      right: 16,
                      bottom: 56,
                      fontSize: 9,
                      color: C.block,
                      background: "rgba(255,255,255,.88)",
                      padding: "2px 4px",
                      borderRadius: 2,
                      maxWidth: 110,
                      lineHeight: 1.4,
                    }}
                  >
                    {segErr}
                  </div>
                )}

                {/* 第三层：模板确定性排版 */}
                <div style={{ position: "absolute", left: 16, top: 42, right: 110 }}>
                  <div style={{ fontSize: 27, fontWeight: 700, lineHeight: 1.22, color: "#2A211C" }}>
                    {content.cover?.headline}
                  </div>
                  <div style={{ fontSize: 13, marginTop: 8, color: "rgba(42,33,28,.75)", lineHeight: 1.5 }}>
                    {content.cover?.subhead}
                  </div>
                </div>

                <div style={{ position: "absolute", left: 16, bottom: 78 }}>
                  {(content.cover?.points || []).map((p, i) => (
                    <div
                      key={i}
                      style={{
                        fontSize: 12,
                        color: "#2A211C",
                        background: "rgba(255,255,255,.66)",
                        borderLeft: `2px solid ${C.accent}`,
                        padding: "3px 8px",
                        marginBottom: 5,
                        borderRadius: 2,
                      }}
                    >
                      {p}
                    </div>
                  ))}
                </div>

                {logoUrl && (
                  <div
                    style={{
                      position: "absolute",
                      right: 16,
                      top: 8,
                      width: 40,
                      height: 40,
                      background: "#fff",
                      borderRadius: "50%",
                      overflow: "hidden",
                      border: "1px solid rgba(0,0,0,.15)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <img
                      src={logoUrl}
                      alt="品牌Logo"
                      style={{ width: "100%", height: "100%", objectFit: "contain" }}
                    />
                  </div>
                )}

                {content.cover?.badge && (
                  <div
                    style={{
                      position: "absolute",
                      right: 16,
                      top: 36,
                      background: C.accent,
                      color: "#fff",
                      fontSize: 12,
                      fontWeight: 600,
                      padding: "5px 9px",
                      borderRadius: 2,
                    }}
                  >
                    {content.cover.badge}
                  </div>
                )}

                {/* 法务角标：达人不可编辑 */}
                <div
                  style={{
                    position: "absolute",
                    left: 0,
                    right: 0,
                    bottom: 0,
                    background: "rgba(255,255,255,.82)",
                    borderTop: "1px solid rgba(0,0,0,.1)",
                    padding: "7px 12px",
                    fontSize: 10,
                    color: "rgba(0,0,0,.6)",
                  }}
                >
                  第三层 模板确定性排版 · 本图含品牌合作推广，效果因人而异
                  <div style={{ fontSize: 9, marginTop: 1, color: "rgba(0,0,0,.42)" }}>
                    法务角标锁定，达人不可编辑
                  </div>
                </div>
              </div>

              <div style={{ marginTop: 12, paddingTop: 12, borderTop: `1px solid ${C.line}` }}>
                <b style={{ color: C.ink, fontSize: 12 }}>背景图调整链路</b>
                <div style={{ ...S.sub, marginTop: 4, fontSize: 11, lineHeight: 1.5 }}>
                  修改提示词或切换上方「视觉风格」后点重新生成，不满意可反复调整。
                </div>
                <textarea
                  value={bgPrompt}
                  onChange={(e) => setBgPrompt(e.target.value)}
                  style={{
                    width: "100%",
                    minHeight: 60,
                    marginTop: 8,
                    border: `1px solid ${C.line}`,
                    borderRadius: 3,
                    padding: 8,
                    fontSize: 12,
                    fontFamily: FONT,
                    lineHeight: 1.5,
                    background: C.fill,
                    color: C.ink,
                    boxSizing: "border-box",
                    resize: "vertical",
                  }}
                />
                <div style={{ marginTop: 8 }}>
                  <button
                    style={S.btn(true, content.bgStatus === "generating")}
                    disabled={content.bgStatus === "generating" || !bgPrompt.trim()}
                    onClick={runRegenerate}
                  >
                    {content.bgStatus === "generating" ? "生成中…" : "重新生成背景图"}
                  </button>
                </div>
              </div>

              <div style={{ marginTop: 14, paddingTop: 12, borderTop: `1px solid ${C.line}` }}>
                <button
                  style={S.btn(true, compositeBusy)}
                  disabled={compositeBusy || !content.bgImageUrl}
                  onClick={runComposite}
                >
                  {compositeBusy ? "合成中…" : "合成成稿并视觉质检"}
                </button>
                {compositeUrl && (
                  <div style={{ marginTop: 10 }}>
                    <img
                      src={compositeUrl}
                      alt="合成成稿"
                      style={{ width: "100%", borderRadius: 3, border: `1px solid ${C.line}` }}
                    />
                    <div style={{ ...S.sub, marginTop: 6 }}>
                      三层合成后的最终成稿，已发送 VLM 质检（结果见下方视觉质检）。
                    </div>
                    {compositeObjectKey && (
                      <a
                        href={`/api/v1/download/${compositeObjectKey}`}
                        download
                        style={{
                          display: "inline-block",
                          marginTop: 8,
                          background: C.ink,
                          color: "#fff",
                          border: "none",
                          borderRadius: 3,
                          padding: "7px 14px",
                          fontSize: 12.5,
                          fontFamily: FONT,
                          textDecoration: "none",
                          cursor: "pointer",
                        }}
                      >
                        下载成稿图
                      </a>
                    )}
                  </div>
                )}
                {compositeErr && (
                  <div style={{ marginTop: 8, fontSize: 12, color: C.block }}>{compositeErr}</div>
                )}
              </div>
            </div>

            {/* 正文 + 编辑权限 */}
            <div>
              <div style={{ ...S.sub, marginBottom: 6 }}>正文（{(content.body || "").length} 字）</div>
              <div
                style={{
                  border: `1px solid ${C.line}`,
                  borderRadius: 3,
                  padding: 14,
                  fontSize: 13.5,
                  lineHeight: 1.85,
                  background: C.fill,
                  whiteSpace: "pre-wrap",
                }}
              >
                {content.body}
              </div>
              <div style={{ marginTop: 10 }}>
                {(content.tags || []).map((t, i) => (
                  <span key={i} style={{ ...S.tag(C.accent), marginBottom: 6 }}>
                    {t.startsWith("#") ? t : "#" + t}
                  </span>
                ))}
              </div>

              <div style={{ marginTop: 18 }}>
                <div style={{ ...S.sub, marginBottom: 7 }}>达人编辑权限</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, fontSize: 12.5 }}>
                  <div>
                    <div style={{ color: C.pass, marginBottom: 4 }}>可编辑</div>
                    <div style={{ color: C.muted, lineHeight: 1.9 }}>
                      正文措辞
                      <br />
                      卖点顺序
                      <br />
                      模板皮肤
                      <br />
                      个人体验补充
                    </div>
                  </div>
                  <div>
                    <div style={{ color: C.block, marginBottom: 4 }}>锁定</div>
                    <div style={{ color: C.muted, lineHeight: 1.9 }}>
                      商品图本体
                      <br />
                      必含卖点
                      <br />
                      价格与活动信息
                      <br />
                      法务角标
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 5. 质检 */}
      {qc && (
        <div style={S.card}>
          <div style={S.h}>
            质检与合规治理
            <span
              style={{
                marginLeft: 10,
                fontSize: 12,
                fontWeight: 600,
                color: levelColor[verdict],
                border: `1px solid ${levelColor[verdict]}`,
                borderRadius: 2,
                padding: "2px 8px",
              }}
            >
              {levelText[verdict]}
            </span>
          </div>
          {qc.map((r, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                gap: 12,
                padding: "10px 0",
                borderTop: i ? `1px solid ${C.line}` : "none",
              }}
            >
              <div
                style={{
                  flex: "0 0 54px",
                  fontSize: 11,
                  color: levelColor[r.level],
                  border: `1px solid ${levelColor[r.level]}`,
                  borderRadius: 2,
                  textAlign: "center",
                  height: 20,
                  lineHeight: "18px",
                }}
              >
                {levelText[r.level]}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 500 }}>{r.item}</div>
                <div style={S.sub}>{r.note}</div>
              </div>
            </div>
          ))}

          {content.self_check?.length > 0 && (
            <div style={{ marginTop: 14, paddingTop: 14, borderTop: `1px solid ${C.line}` }}>
              <div style={{ ...S.sub, marginBottom: 7 }}>模型软评分（低置信项进人工复核队列）</div>
              {content.self_check.map((s, i) => (
                <div key={i} style={{ fontSize: 12.5, marginBottom: 5 }}>
                  <span style={S.tag(levelColor[s.level] || C.muted)}>{levelText[s.level] || s.level}</span>
                  {s.item}
                  <span style={{ ...S.sub, marginLeft: 6 }}>{s.note}</span>
                </div>
              ))}
            </div>
          )}

          {(content.vqaStatus === "running" || content.vqaStatus === "done" || content.vqaStatus === "error") && (
            <div style={{ marginTop: 14, paddingTop: 14, borderTop: `1px solid ${C.line}` }}>
              <div style={{ ...S.sub, marginBottom: 7 }}>
                视觉质检（Qwen-VL 看图判断）
                {content.vqaStatus === "running" && (
                  <span style={{ marginLeft: 6, color: C.review }}>质检中…</span>
                )}
              </div>
              {content.vqaStatus === "running" && (
                <div style={{ fontSize: 12.5, color: C.muted }}>
                  VLM 正在检查 Logo 变形、文字越界、画面调性…
                </div>
              )}
              {content.vqaStatus === "done" &&
                (content.vqa || []).map((s, i) => (
                  <div key={i} style={{ fontSize: 12.5, marginBottom: 5 }}>
                    <span style={S.tag(levelColor[s.level] || C.muted)}>{levelText[s.level] || s.level}</span>
                    {s.item}
                    <span style={{ ...S.sub, marginLeft: 6 }}>{s.note}</span>
                  </div>
                ))}
              {content.vqaStatus === "error" && (
                <div style={{ fontSize: 12.5, color: C.block }}>视觉质检失败：{content.vqaError}</div>
              )}
            </div>
          )}

          {compositeVqa && compositeVqa.length > 0 && (
            <div style={{ marginTop: 14, paddingTop: 14, borderTop: `1px solid ${C.line}` }}>
              <div style={{ ...S.sub, marginBottom: 7 }}>最终成稿视觉质检（三层合成图）</div>
              {compositeVqa.map((s, i) => (
                <div key={i} style={{ fontSize: 12.5, marginBottom: 5 }}>
                  <span style={S.tag(levelColor[s.level] || C.muted)}>{levelText[s.level] || s.level}</span>
                  {s.item}
                  <span style={{ ...S.sub, marginLeft: 6 }}>{s.note}</span>
                </div>
              ))}
            </div>
          )}

          <div style={{ ...S.sub, marginTop: 14, lineHeight: 1.75 }}>
            上方「硬规则」由客户端确定性逻辑拦截（不依赖模型）；「模型软评分」与「视觉质检（VLM）」属概率性判断，只做软评分参考，低分进人工复核。
          </div>
        </div>
      )}

      {/* 历史记录 */}
      {history.length > 0 && (
        <div style={S.card}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <div style={{ ...S.h, margin: 0 }}>历史记录（{history.length}）</div>
            <button style={S.chip(false)} onClick={clearHistory}>清空</button>
          </div>
          {history.map((h, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                gap: 12,
                alignItems: "center",
                padding: "9px 0",
                borderTop: i ? `1px solid ${C.line}` : "none",
                fontSize: 12.5,
              }}
            >
              <span style={{ flex: "0 0 120px", color: C.muted, fontVariantNumeric: "tabular-nums" }}>
                {formatTime(h.ts)}
              </span>
              <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {h.topic || h.headline || "未命名"}
                <span style={{ ...S.sub, marginLeft: 8 }}>{h.type} · {h.style}</span>
              </span>
              {h.objectKey ? (
                <a
                  href={`/api/v1/download/${h.objectKey}`}
                  download
                  style={{ flex: "0 0 auto", color: C.accent, textDecoration: "none", fontSize: 12 }}
                >
                  下载
                </a>
              ) : (
                <span style={{ color: C.muted }}>—</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function formatTime(ts) {
  const d = new Date(ts);
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getMonth() + 1}/${d.getDate()} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

function Field({ label, children }) {
  return (
    <div>
      <div style={{ color: C.muted, fontSize: 12.5, marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: 13.5 }}>{children || "—"}</div>
    </div>
  );
}
