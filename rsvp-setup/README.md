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

Copy the URL Cloudflare prints; it ends with `.workers.dev`. The invitation's `index.html` is already set to:

```js
const API_BASE = 'https://lee-valdez-rsvp.keilyv.workers.dev';
```

If you deploy this kit to a different Cloudflare account, replace that URL with your own Worker URL, without a slash at the end. Save the file.

## 4. Update the website

In Terminal, go back to the `lee-valdez-wedding` folder, then push the site and service code:

```sh
cd ..
git add index.html .gitignore rsvp-setup/schema.sql rsvp-setup/wrangler.jsonc rsvp-setup/wrangler.example.jsonc rsvp-setup/worker.js rsvp-setup/create_links.py rsvp-setup/guests.example.csv rsvp-setup/README.md
git commit -m "Add personalized RSVP service"
git push
```

After GitHub Pages updates, open a URL from your private `links.csv`. It should show the household name and only allow up to its allocated guest count. Submit a test RSVP and check Cloudflare **D1 > wedding-rsvps > Console** with:

Guests who accept choose how many are attending and enter one name for each person. An invitation for two can RSVP for one and will then show only one required name field. Existing responses with blank names will ask for names the next time the guest updates their RSVP. This uses the existing database columns; you do not need to rerun `schema.sql` or import `invites.sql`.

```sql
SELECT household_name, attendance, guest_count, guest_names, dietary_notes, message, responded_at FROM invitations;
```

This test also shows how to view responses later. Send the right URL from `links.csv` to each household privately. Guests can reopen their link to change their response.

## 5. Export a private Excel report

From `rsvp-setup`, run:

```sh
python3 export_responses.py
```

This reads the current RSVP responses and creates a formatted `.xlsx` report in `wedding-rsvp-private`, beside your repository. It includes a summary and a filterable list of households, guest counts, names, dietary notes, messages, and response times. Run the same command whenever you want a fresh report. Keep the report private, and do not move it into the GitHub repository.

## 6. Get a phone alert for each RSVP

Install Telegram on your phone. In Telegram, open the official `@BotFather`, send `/newbot`, and follow its prompts to make your own private RSVP bot. Open your new bot and tap **Start**. From `rsvp-setup` on your Mac, run:

```sh
python3 setup_notifications.py
```

Paste the BotFather token when the script asks; the input is hidden. The script identifies your private chat, sends a test message, stores the bot token and chat ID as encrypted Cloudflare Worker secrets, and deploys the notification-enabled Worker. Keep the bot token private and out of the GitHub repository. When a guest submits or updates an RSVP, you receive the household name and attending/declined status in Telegram. Dietary notes, messages, and guest links are not sent there. If Telegram is temporarily unavailable, the RSVP still saves in D1; check your Excel export for the complete record.

## Practical limits

- A link acts as a key. Anyone who receives or is forwarded that link can view and change that household's RSVP. Avoid posting links publicly.
- This system enforces a **maximum number** of people per household. It does not verify each person's identity.
- Cloudflare's free plan has request and database usage limits. If a limit is reached, new RSVPs may fail until the quota resets. Monitor the Cloudflare dashboard as the wedding approaches.
- If you create a new guest after setup, create a new private token and insert just that household rather than rerunning the full generator over old households.
- The free service sends no automatic confirmation emails; the page shows a confirmation after a successful save.
