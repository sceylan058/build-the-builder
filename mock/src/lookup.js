// Data-driven lookup over the bank's test customers: service -> customerNo -> masked card -> (week) -> {http, response, delaySeconds}.
// No routing here: index.js maps HTTP paths/fields to (service, customerNo, card, week) once the integration document is known.
import DATA from "./test-customers.json" with { type: "json" };

const BY_CUSTOMER = new Map(DATA.customers.map((c) => [String(c.customerNo), c]));
const CARD_SERVICES = new Set(["cards.balance", "statement.week.get", "statement.week.decide", "statement.week.change"]);
const WEEK_SERVICES = new Set(["statement.week.decide", "statement.week.change"]);

const digits = (s) => String(s ?? "").replace(/\D/g, "");

// A request may carry the masked number from cards.list ("540000******1234"), another masking ("5400********1234"),
// the full number, or only the last 4/6 digits. Match the entry key whose visible digits agree with the request.
export function matchCard(keys, requested) {
  if (requested == null || requested === "") return null;
  const req = String(requested).trim();
  if (keys.includes(req)) return req;
  const rd = digits(req);
  const cands = keys.filter((k) => {
    const kd = digits(k);
    const tailLen = (k.match(/\d+$/) || [""])[0].length;
    if (!rd || rd.length < 4) return false;
    if (rd.slice(-Math.min(tailLen, rd.length)) !== kd.slice(-Math.min(tailLen, rd.length))) return false;
    const head = (k.match(/^\d+/) || [""])[0];
    if (rd.length >= 15 && head && !rd.startsWith(head)) return false;
    return true;
  });
  return cands.length === 1 ? cands[0] : null;
}

function errorBody(code, text, type = "WARNING") {
  const guid = "00000000000000000000000000000000";
  return { result: { guid, returnCode: code, messageText: text, code, message: text, type, details: { guid, rootCause: null, errorOrigin: null } } };
}

export function lookup(service, customerNo, card, week) {
  const cust = BY_CUSTOMER.get(String(customerNo ?? "").trim());
  if (!cust) return { http: 404, response: errorBody("MOCK_CUSTOMER_NOT_FOUND", "Müşteri bulunamadı.") };
  let node = cust.services[service];
  if (node === undefined) return { http: 404, response: errorBody("MOCK_SERVICE_NOT_FOUND", "Servis bu müşteri için tanımlı değil.") };
  if (CARD_SERVICES.has(service)) {
    const key = matchCard(Object.keys(node), card);
    if (!key) return { http: 404, response: errorBody("MOCK_CARD_NOT_FOUND", "Kart bulunamadı.") };
    node = node[key];
  }
  if (WEEK_SERVICES.has(service)) {
    const w = String(week ?? "").trim();
    if (!(w in node)) return { http: 400, response: errorBody("MOCK_WEEK_INVALID", "Geçersiz hafta.") };
    node = node[w];
  }
  return { http: node.http, response: node.response, delaySeconds: node.delaySeconds || 0 };
}

export const SERVICES = ["cards.list", "contact.email.get", "cards.balance", "statement.week.get", "statement.week.decide", "statement.week.change", "statement.pdf.send"];
