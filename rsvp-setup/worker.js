// Only this Worker can read the guest list. Do not put invite tokens or names in GitHub.
const SITE_ORIGIN = 'https://keilyv.github.io';

function reply(data, status = 200, origin = '') {
  const headers = {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
  };
  if (origin === SITE_ORIGIN) {
    headers['Access-Control-Allow-Origin'] = SITE_ORIGIN;
    headers['Vary'] = 'Origin';
  }
  return new Response(JSON.stringify(data), { status, headers });
}

async function hashToken(token) {
  const bytes = new TextEncoder().encode(token);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
}

async function sendRsvpAlert(result, env) {
  if (!env.TELEGRAM_BOT_TOKEN || !env.TELEGRAM_CHAT_ID) return;
  const answer = result.attendance === 'attending'
    ? `Attending: ${result.guest_count} guest${result.guest_count === 1 ? '' : 's'}`
    : 'Declined';
  try {
    const response = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: env.TELEGRAM_CHAT_ID,
        text: `Wedding RSVP received\n${result.household_name}\n${answer}`,
      }),
    });
    if (!response.ok || !(await response.json()).ok) {
      console.error('RSVP alert was not delivered');
    }
  } catch {
    // A Telegram outage must never erase a guest's saved RSVP.
    console.error('RSVP alert was not delivered');
  }
}

export default {
  async fetch(request, env, ctx) {
    const origin = request.headers.get('Origin') || '';
    const pathname = new URL(request.url).pathname;
    if (request.method === 'OPTIONS') {
      if (origin !== SITE_ORIGIN) return reply({ error: 'Forbidden' }, 403);
      return new Response(null, { status: 204, headers: {
        'Access-Control-Allow-Origin': SITE_ORIGIN,
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Max-Age': '3600',
        'Vary': 'Origin',
      } });
    }
    if (origin !== SITE_ORIGIN) return reply({ error: 'Forbidden' }, 403);
    if (request.method !== 'POST' || !['/invite', '/rsvp'].includes(pathname)) return reply({ error: 'Not found' }, 404, origin);
    if (!(request.headers.get('Content-Type') || '').startsWith('application/json')) return reply({ error: 'JSON required' }, 415, origin);
    if (Number(request.headers.get('Content-Length')) > 4096) return reply({ error: 'Request too large' }, 413, origin);

    let input;
    try { input = await request.json(); } catch { return reply({ error: 'Invalid JSON' }, 400, origin); }
    if (!input || typeof input.token !== 'string' || !/^[A-Za-z0-9_-]{32}$/.test(input.token)) {
      return reply({ error: 'Invalid invitation link' }, 400, origin);
    }
    const tokenHash = await hashToken(input.token);
    try {
      if (pathname === '/invite') {
        const row = await env.DB.prepare(
          'SELECT household_name, max_guests, attendance, guest_count, guest_names, dietary_notes, message FROM invitations WHERE token_hash = ? AND active = 1'
        ).bind(tokenHash).first();
        if (!row) return reply({ error: 'Invitation not found' }, 404, origin);
        return reply(row, 200, origin);
      }

      const attendance = input.attendance;
      if (!['attending', 'declined'].includes(attendance)) return reply({ error: 'Choose attending or declining' }, 400, origin);
      const guestCount = attendance === 'declined' ? 0 : Number(input.guest_count);
      const guestNames = attendance === 'declined' ? '' : input.guest_names;
      const dietaryNotes = attendance === 'declined' ? '' : input.dietary_notes;
      const message = input.message;
      if (!Number.isInteger(guestCount) || guestCount < (attendance === 'attending' ? 1 : 0) || guestCount > 20 ||
          typeof guestNames !== 'string' || guestNames.trim().length > 1619 ||
          typeof dietaryNotes !== 'string' || dietaryNotes.trim().length > 500 ||
          typeof message !== 'string' || message.trim().length > 500) {
        return reply({ error: 'Check your response and try again' }, 400, origin);
      }
      const names = attendance === 'attending' ? guestNames.split(/\r?\n/).map(name => name.trim()) : [];
      if (attendance === 'attending' &&
          (names.length !== guestCount || names.some(name => !name || name.length > 80))) {
        return reply({ error: 'Enter one name for each person attending' }, 400, origin);
      }
      const result = await env.DB.prepare(
        `UPDATE invitations SET attendance = ?, guest_count = ?, guest_names = ?, dietary_notes = ?, message = ?, responded_at = datetime('now')
         WHERE token_hash = ? AND active = 1 AND max_guests >= ? RETURNING household_name, max_guests, attendance, guest_count, guest_names, dietary_notes, message`
      ).bind(attendance, guestCount, names.join('\n'), dietaryNotes.trim(), message.trim(), tokenHash, guestCount).first();
      if (!result) return reply({ error: 'Invitation not found or guest count exceeds your invitation' }, 400, origin);
      if (env.TELEGRAM_BOT_TOKEN && env.TELEGRAM_CHAT_ID) {
        ctx.waitUntil(sendRsvpAlert(result, env));
      }
      return reply(result, 200, origin);
    } catch {
      return reply({ error: 'RSVP is temporarily unavailable. Please try again later.' }, 503, origin);
    }
  },
};
