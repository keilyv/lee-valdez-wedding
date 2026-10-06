# Personalized wedding RSVPs

Your GitHub Pages invitation stays where it is. A free Cloudflare Worker receives RSVPs and stores them in a D1 database. Each household gets a random private link and a guest limit. The public repository contains no real guest names or private links.

## 1. Set up the database

Create a free Cloudflare account. Install Node.js on your Mac if the `npx` command is unavailable. In Terminal, open the `rsvp-setup` folder within your `lee-valdez-wedding` repository:

```sh
cd rsvp-setup
npx wrangler login
npx wrangler d1 create wedding-rsvps
```

Cloudflare prints a `database_id` (a UUID). Create a configuration file from the example:

```sh
cp wrangler.example.jsonc wrangler.jsonc
```

Open `wrangler.jsonc` in a text editor and replace `PASTE_DATABASE_ID_HERE` with that ID. Then run:

```sh
npx wrangler d1 execute wedding-rsvps --remote --file=schema.sql
```

## 2. Create your guest list privately

Create a CSV file **outside** the public `lee-valdez-wedding` folder, for example `wedding-guests.csv` next to it. Use exactly these column headings:

```csv
household_name,max_guests
Example Household,2
```

Replace the example with your own households and invitation sizes. One link is created per CSV row. From inside `rsvp-setup`, run:

```sh
python3 create_links.py ../../wedding-guests.csv --output ../../wedding-rsvp-private
```

This creates a private `links.csv` and `invites.sql` **next to**, rather than inside, the GitHub repository. Keep `links.csv` somewhere only you can access. Don't put either file or the real guest list on GitHub. Don't rerun the generator after sending invitations; it creates new tokens each time.

Import the invitations into D1:

```sh
npx wrangler d1 execute wedding-rsvps --remote --file=../../wedding-rsvp-private/invites.sql
```

## 3. Deploy the RSVP service

From `rsvp-setup`, run:

```sh
npx wrangler deploy
```

Copy the URL Cloudflare prints; it ends with `.workers.dev`. In the `index.html` file in the parent folder, find:

```js
const API_BASE = '';
```

Paste your Worker URL between the quotes, without a slash at the end. For example: `const API_BASE = 'https://lee-valdez-rsvp.YOUR-NAME.workers.dev';`. Save the file.

## 4. Update the website

In Terminal, go back to the `lee-valdez-wedding` folder, then push the site and service code:

```sh
cd ..
git add index.html .gitignore rsvp-setup/schema.sql rsvp-setup/wrangler.jsonc rsvp-setup/wrangler.example.jsonc rsvp-setup/worker.js rsvp-setup/create_links.py rsvp-setup/guests.example.csv rsvp-setup/README.md
git commit -m "Add personalized RSVP service"
git push
```

After GitHub Pages updates, open a URL from your private `links.csv`. It should show the household name and only allow up to its allocated guest count. Submit a test RSVP and check Cloudflare **D1 > wedding-rsvps > Console** with:

```sql
SELECT household_name, attendance, guest_count, guest_names, dietary_notes, message, responded_at FROM invitations;
```

This test also shows how to view responses later. Send the right URL from `links.csv` to each household privately. Guests can reopen their link to change their response.

## Practical limits

- A link acts as a key. Anyone who receives or is forwarded that link can view and change that household's RSVP. Avoid posting links publicly.
- This system enforces a **maximum number** of people per household. It does not verify each person's identity.
- Cloudflare's free plan has request and database usage limits. If a limit is reached, new RSVPs may fail until the quota resets. Monitor the Cloudflare dashboard as the wedding approaches.
- If you create a new guest after setup, create a new private token and insert just that household rather than rerunning the full generator over old households.
- The free service sends no automatic confirmation emails; the page shows a confirmation after a successful save.
