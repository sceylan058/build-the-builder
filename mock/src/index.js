// Freya Bank statement-debt mock (Cloudflare Worker). Data-driven: every answer comes from test-customers.json.
// Routing is tolerant until the service contract fixes the exact paths: any POST whose last path segment is a
// service name (e.g. /voice/v1/cards.list) is served. Body: {"data": {...}, "call": {...}} as in the bank's contract.
import DATA from "./test-customers.json";

const SERVICES = ["cards.list", "contact.email.get", "cards.balance", "statement.week.get", "statement.week.decide", "statement.week.change", "statement.pdf.send"];
const CARD_SERVICES = new Set(["cards.balance", "statement.week.get", "statement.week.decide", "statement.week.change"]);
const WEEK_SERVICES = new Set(["statement.week.decide", "statement.week.change"]);
const BY_CUSTOMER = new Map(DATA.customers.map((c) => [String(c.customerNo), c]));
const CORS = { "Access-Control-Allow-Origin": "*" };
const digits = (s) => String(s ?? "").replace(/\D/g, "");
const isTpl = (v) => typeof v === "string" && (v.includes("{{") || v.includes("%7B%7B"));

function json(body, status = 200) { return Response.json(body, { status, headers: CORS }); }

function errorBody(code, text, type = "WARNING") {
  const guid = "00000000000000000000000000000000";
  return { result: { guid, returnCode: code, messageText: text, code, message: text, type, details: { guid, rootCause: null, errorOrigin: "freya-mock" } } };
}

function matchCard(keys, requested) {
  if (requested == null || requested === "" || isTpl(requested)) return keys.length ? keys[0] : null;
  const req = String(requested).trim();
  if (keys.includes(req)) return req;
  const rd = digits(req);
  if (rd.length < 4) return null;
  const cands = keys.filter((k) => {
    const kd = digits(k);
    const tail = (k.match(/\d+$/) || [""])[0];
    const n = Math.min(tail.length, rd.length);
    if (rd.slice(-n) !== kd.slice(-n)) return false;
    const head = (k.match(/^\d+/) || [""])[0];
    if (rd.length >= 15 && head && !rd.startsWith(head)) return false;
    return true;
  });
  return cands.length === 1 ? cands[0] : null;
}

function pick(obj, names) {
  for (const n of names) if (obj && obj[n] !== undefined && obj[n] !== null && obj[n] !== "") return obj[n];
  return undefined;
}

function lookup(service, body) {
  const d = (body && typeof body.data === "object" && body.data) || body || {};
  let customerNo = pick(d, ["customerNo", "customerNumber", "musteriNo"]);
  if (customerNo === undefined || isTpl(customerNo)) customerNo = isTpl(customerNo) ? "90000001" : customerNo;
  const cust = BY_CUSTOMER.get(digits(customerNo));
  if (!cust) return { http: 404, response: errorBody("FB_IVR_CHANNEL_102", "Müşteri bulunamadı.") };
  let node = cust.services[service];
  if (node === undefined) return { http: 404, response: errorBody("FB_IVR_CHANNEL_102", "Kayıt bulunamadı.") };
  if (CARD_SERVICES.has(service)) {
    const key = matchCard(Object.keys(node), pick(d, ["cardNumber", "cardNo", "maskedCardNumber", "cardNumberLast4"]));
    if (!key) return { http: 404, response: errorBody("FB_IVR_CHANNEL_102", "Kart bulunamadı.") };
    node = node[key];
  }
  if (WEEK_SERVICES.has(service)) {
    const w = String(pick(d, ["newStatementWeek", "statementWeek", "week"]) ?? "").trim();
    const key = w in node ? w : (isTpl(w) ? Object.keys(node)[0] : null);
    if (!key) return { http: 400, response: errorBody("FB_IVR_CHANNEL_400", "Geçersiz hafta.") };
    node = node[key];
  }
  return { http: node.http, response: node.response ?? node.yanit, delay: node.delaySeconds || node.gecikmeSaniye || 0 };
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") return new Response(null, { headers: { ...CORS, "Access-Control-Allow-Methods": "GET, POST, OPTIONS", "Access-Control-Allow-Headers": "*" } });
    if (url.pathname === "/health") return json({ status: "ok", services: SERVICES });
    const service = url.pathname.split("/").filter(Boolean).pop() || "";
    if (request.method === "POST" && SERVICES.includes(service)) {
      let body = null;
      try { body = await request.json(); } catch { body = {}; }
      const r = lookup(service, body);
      if (r.delay) await new Promise((res) => setTimeout(res, r.delay * 1000));
      return json(r.response, r.http);
    }
    return json(errorBody("NOT_FOUND", "Yol bulunamadı."), 404);
  },
};
