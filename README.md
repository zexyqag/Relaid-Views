# Relaid views

Views of apps for Relaid. Relaid shows a phone app's screen on another device by its meaning (its
buttons, fields and text, read through Android accessibility) rather than as pixels. Any app works
plain; a view makes one app's screens read the way someone wants them to.

A view is data, never code. It points at parts of a screen and says how to present them. It cannot
run anything on the phone.

An app can have several views side by side: a full one, a minimal one with only chats, and so on.
Each comes as a pack. The owner installs the ones they like, picks each app's default, and can open
or pin any view on its own. Relaid adds views of every app itself: `plain` (no pack), `pictures`
(the whole screen as a live picture, where the owner allows it) and, on a computer, `video` (the
phone's own screen in a scrcpy window, where the owner set it up). What any installed view
guards (a screen kept secure, a slide to approve, the code entry) holds in every view of its app.

## Layout

```
packs/<app package>/<view>/pack.json      app, view, name, version, description, permissions
packs/<app package>/<view>/view.json      the app's skin and its screens (see below)
packs/<app package>/<view>/fixtures/      captured screens and what the view must make of them
index.json                                built from the packs; pins each view.json by SHA-256
tools/check.py                            the check (Python 3, standard library only)
```

A view's name (the folder, and `view` in pack.json) is lowercase letters, digits and dashes, and
never `plain`, `pictures` or `video`. A pack's `name` is what people see, so an app's views need distinct
names ("Snapchat", "Snapchat, chats only").

A phone installs a pack only if its view.json matches the hash in index.json, then checks the
rules again itself.

## The view file

```json
{
  "theme": { "accent": "#5a78ff" },
  "screens": [
    {
      "name": "chat",
      "displayName": "Chat",
      "when": ["id:message_list"],
      "parts": [
        { "select": "id:message_list", "as": "list", "scroll": "drag" },
        { "select": "class:Label & in(id:message_list)", "as": "text" },
        { "select": "id:sender & in(id:message_list)", "as": "heading" },
        { "select": "id:camera_button", "as": "hidden" }
      ]
    }
  ]
}
```

A screen applies when all of its `when` selectors match (the highest `priority`, then the most
selectors, wins). A screen with no `when` would claim every screen of its app, the ones its author
never saw too, so it is refused unless it is `secure` and holds only what protects the person (an
`action` with `confirm: "slide"` or a swipe to `perform`, and `pin`): a view may keep every screen of
its app secure, with its slides to approve, but never shape screens it was not written for. Such a
screen holds wherever it matches, whichever of the view's screens applies there (one written for that
page too), so a screen with `when` need not repeat its slides. Its
`parts` are one list of rules: each says what the nodes its `select` matches are, with `as`. A rule
without `as` leaves the part where it stands and says only what Relaid cannot read there: a
`label` for a part that shows no words of its own and holds no field or switch (a picture's place,
an icon button the app names nowhere), and a `tone` for a control, which is then drawn as a button
in that tone where the app draws it.
Without a view Relaid still shows the screen plain: the main list, the header and footer around it,
the title, icon buttons in the header as a menu, the bottom navigation as tabs. A view is for what
that plain reading gets wrong, or shows differently from how you want it, so write only the rules a
screen needs.

| Screen field | Meaning |
|---|---|
| `name` | Stable id: lowercase letters, digits and dashes. The owner can switch a screen off by it |
| `displayName` | What people see: one line, at most 60 characters |
| `when` | Selectors that must all match for the screen to apply: at least one, unless the screen is `secure` and holds only slides, swipes and `pin` |
| `activity` | Part of the window's activity name, where `when` cannot tell screens apart |
| `secure` | Mark the screen secure when the app gives no signal for it |
| `priority` | Breaks ties when several screens match |
| `phone` | The whole screen needs the phone itself (a camera's viewfinder, a chip held to it), for one of Relaid's reasons (see below). Never on a screen with no `when`. Pack format 4 |
| `page` | The page the screen is drawn on, where the app draws it otherwise than its others: `accent`, the whole page in the theme's accent (see below). Never on a screen with no `when`. Pack format 5 |
| `parts` | The rules, in order |

| `as` | Meaning | Options |
|---|---|---|
| `hidden` | Left out: ads, decoration, duplicates | |
| `text` | Shown as text, never as a control (an app that offers a click on every message), with everything in it | |
| `heading` | Shown as a section heading (who wrote the messages below, a date), with everything in it never a control | |
| `picture` | Shown as a picture, captured live from the app's own window. Only a part with no text and no control in it. Needs the permission `pictures` | `label`: named until the picture arrives |
| (none) | The part where it stands. `label`: its words, where it shows none of its own and holds no field or switch (an icon button, a meter, a picture's place). `tone`: a control drawn as a button in that tone where the app draws it (an app's filled pill in its page, in a list too), where it has one line of words and is no switch; one whose words destroy or refuse stays `destructive`, and `secondary` there draws it as an outline in Relaid's red. Pack format 3 for both. `phone`: the control needs the phone itself (pack format 4). `icon`: one of Relaid's icons beside its words (pack format 5). `look`: how the app draws a button there, which its tree does not tell (pack format 6) | `label`, `tone`: `primary`, `secondary`, `muted`, `destructive`; `phone`; `icon`; `look`: `link` |
| `title` | The screen's title | |
| `hero` | Shown large and centred (an amount): text, a heading or a field | |
| `list` | The main list | `scroll: "drag"`: Relaid drags it, for an app that ignores the scroll Relaid sends. Needs `touch` |
| `field` | An input | `label` where the app gives none (no hint, no label drawn in it, nor one drawn right above it, which names it and then shows only as its name); `keyboard`: `number`, `phone`, `email`, `text` |
| `action` | A control in the bottom bar | `label` where the app shows none; `tone`: `primary`, `secondary`, `muted`, `destructive`; `confirm: "slide"`: a deliberate slide, and the screen is secure; `perform`: `click`, `swipe-right`, `swipe-left`, `swipe-up`, `swipe-down` (Relaid swipes the control; needs `touch`); `phone` and `icon` (never with a slide or a swipe) |
| `option` | A control in the menu | `label`, `tone`, `phone`, `icon` |
| `tab` | The app's bottom navigation, in rule order. A tab with nothing to press is the current one | `label` where the app shows none; `icon` (a tab's own): `home`, `list`, `people`, `person`, `wallet`, `card`, `search`, `settings`, `bell`, `chart`, `star`, `chat`, `grid` |
| `person` | A row about a person, shown with a round avatar of its own initials | |
| `row` | A list row the app builds from separately pressable parts (an avatar, a name, a status) with none of them the row: shown as one item, the first part its title, the rest its second line | `parts`: the nodes whose text it shows (default every text); `press`: the node whose control a press goes to |
| `pin` | The app's own "N of M entered" node: only the counts cross over, never digits. If the app reports no count, select the code field and give `total`: the phone counts the person's own key presses. A code field with visible text is never replaced | `label` (without one, the app's own words drawn right above it name it, if any, but never the screen's title), `total` (1 to 12) |
| `card` | A box the app draws parts in, shown as a card around them (a service's name and its question). Pack format 5 | |
| `note` | A box the app draws parts in, shown as a note: a tinted panel with Relaid's own info icon (an info box). Pack format 5 | |
| `unread` | Where on this screen Relaid looks for what it cannot read (photos drawn in a view of their own, a map, a chart), to show as pictures, where the owner chose that for the app. A screen a view knows gets such pictures only inside its `unread` parts, and none without them; screens no view knows, anywhere. An `unread` part inside a pressable list row is that row's thumbnail (a photo, album art). It only narrows the owner's choice, so it needs no permission. Pack format 2 | |

`title`, `hero`, `list` and `pin` appear at most once per screen.

### What needs the phone itself

Some of an app's flows can only be done at the phone: reading a passport's chip, the camera for a
code, a fingerprint, another app, a file. A view says so with `phone`, on a control (a rule without
`as`, an `action` or an `option`) or on a whole screen, giving one of Relaid's reasons, never words of
its own: every device shows "On the phone:" and Relaid's words for it where the control or the screen
stands, and asks before it presses such a control. The press still goes, so the owner may start it
from a device and finish it at the phone. Pack format 4.

| `phone` | Every device says |
|---|---|
| `camera` | On the phone: uses the camera |
| `chip` | On the phone: reads a passport's or a card's chip |
| `fingerprint` | On the phone: asks for a fingerprint or a face |
| `app` | On the phone: uses another app |
| `file` | On the phone: picks a file |
| `permission` | On the phone: asks for a permission |

The mark never goes on what protects the person: a view may not give `phone` to an `action` with
`confirm: "slide"` or a swipe to `perform`, nor to a `field`, `pin` or `tab`, and Relaid marks no key
of a keypad. It hides, moves and renames nothing, so unlike the other rules where a part stands it
holds on secure screens too.

### Icons, links, boxes and pages

A view may ask for some of the app's look in Relaid's own terms, never with its own drawings or colours beyond its theme. Like
`phone`, icons, boxes and pages hide, move and rename nothing, so they hold on secure screens too; a link's look does not.

- `icon`, on a rule without `as`, an `action` or an `option`: one of Relaid's icons, drawn beside the control's words, never
  instead of them (they always show). Before the words: `close`, `help`, `document`, `download`, `external`; after them: `menu`,
  `next`, `settings`, `save`, `remove`. Never on a slide or a swipe; Relaid itself never draws one on a field, a key of a keypad,
  a control the app draws as a large tile (whose card shows its words alone) or a control that destroys or refuses, whose only
  mark is Relaid's own.
- `look: "link"`, on a rule without `as`: the app draws the button there as a text link, its words alone with no box (a quiet Back
  under a page's pills): its tree draws a text button and an outlined one alike, so only a view can say it. Devices draw its words
  underlined in its tone's colour (the accent, muted where its tone is muted), no box around them. A look shapes what is shown, so
  like a tone it is ignored on a secure screen; never on a control whose words destroy or refuse (drawn as Relaid draws them), one
  that asks for a slide, one in a bar or a tile. Pack format 6.
- `card` and `note`: the box the app draws parts in. Its parts stay where they are in reading order, inside a card, or inside a note
  (a panel tinted with the accent, Relaid's info icon at its start). A part a bar takes (the bottom bar, the top bar, the way back)
  stays out of it.
- `page: "accent"` on a screen: the whole page in the theme's accent (each scheme's palette accent, else the theme's), its words in
  its `onAccent` (else white or near-black, whichever reads better), its controls in those words with the accent on them, and a
  keypad's keys straight on it. Relaid builds that page from the theme and checks it as any palette (its words 4.5:1 on it, one of
  Relaid's reds 3:1); where it fails in either scheme, the screen is drawn in the theme as it is.

A row whose words the app gives as one description of two sentences while it draws them as two texts one above the other (a
menu's title and its line under it) reads as those two by itself: no view needs to split it. Words that ask for a slide stay
whole, so the slide they ask for holds.

A page of the app that none of a view's screens with `when` matches is shown as Relaid reads any
app, and every device says so quietly in the session's menu: "Read plainly: not in" and the view's
name. A screen with no `when` (one that keeps every screen secure) makes no page less so.

A screen a view knows gets the owner's pictures of what Relaid cannot read only inside its `unread`
parts: its author has seen that screen and says where they belong, as the plain reading's own
guesses show odd pieces of some apps (a chat's bubbles). A screen no view knows gets them anywhere.

`theme`, the app's skin, applies to every screen of the app: `accent`; `light` and `dark` palettes
(`accent`, `background`, `surface`, `text`, `muted`, `onAccent`); `corners` (`square`, `rounded`,
`round`); `header` (`bar`, `plain`, `accent`); `cards` (`outlined`, `filled`, `flat`).

## Selectors

A selector is one or more conditions joined with ` & `; a node must meet all of them.

| Condition | Matches a node |
|---|---|
| `id:send` | whose view id ends in `/send` (or is exactly `com.app:id/send`) |
| `id~:pill-` | whose view id contains `pill-` |
| `text:Send`, `text~:send` | whose text (or description, where it has no text) is "Send" ignoring case, or contains it |
| `desc:More`, `desc~:more` | the same, on the description only |
| `class:EditText` | whose class name ends in `EditText` |
| `is:clickable` | in that state: `clickable`, `long-clickable`, `editable`, `scrollable`, `checkable`, `checked`, `selected`, `focused`, `heading`, `password` |
| `in(S)` | inside a node matching selector S |
| `parent(S)` | directly inside a node matching S |
| `has(S)` | with a node matching S inside it |
| `not(S)` | not matching S |
| `nth:2` | the second child of its parent |

Parentheses inside a value must balance, and ` & ` cannot appear in a value. Prefer ids and structure
to visible text, which changes with the phone's language.

## Rules

- One pack per view of an app; it shapes only that app.
- Relaid reads packs strictly: a key, value or option it does not know (a typo, or a feature of a
  newer Relaid) makes it refuse the whole pack, never quietly drop that part. Each pack's `format`
  in `index.json` says which Relaid can read it; `tools/check.py` works it out from the features the
  pack uses. A Relaid that does not read a pack's format says so ("needs a newer Relaid") and keeps
  any version of the pack it already has.
- A label from a view is only used where the app shows no text of its own. A view can name an
  unlabelled button, where it stands or in a bar, but it cannot rename one.
- A view can add friction (`confirm: "slide"`, `secure`) but never remove it, and what one installed
  view of an app adds holds in all its views. A control whose words destroy or refuse is drawn
  `destructive`, with Relaid's red and mark, whatever `tone` a view gives it.
- On a secure screen nothing can be hidden or reshaped: `hidden`, `text`, `heading`, `picture`, `row`
  and rules without `as` (labels, tones and looks where a part stands; a `phone` or an `icon` still holds, as do `card` and `note`) are ignored there, and Relaid never
  touches or captures. Relaid marks a screen secure when it has a password field, a PIN pad, or a
  control that asks for a swipe or that a pack declares a slide, whatever the pack says otherwise;
  `secure` can mark more screens, never fewer.
- The skin applies to the whole screen by role, never to one control, and Relaid ignores any part
  that breaks these rules:
  - colours are `#RRGGBB`;
  - an accent may be any colour, a red brand's own red too: a control that destroys or refuses is
    told apart by Relaid's own mark (a warning triangle) and its words, never by colour alone, and is
    always drawn in one of Relaid's own reds, never the view's;
  - a palette has `background`, `surface`, `text` and `muted`, and an accent (its own or the
    theme's); text and muted text reach 4.5:1 against background and surface, the accent reaches
    3:1, and `onAccent` (text on accent buttons, optional) reaches 3:1 against the accent;
  - one of Relaid's reds reaches 3:1 against the palette's background and surface: devices draw a
    destructive control in the first that does, from Relaid's reds for a light page where black
    words read better on the background than white ones, else from its reds for a dark page (each
    list going further from that page), with white or near-black words, whichever reads better on
    it. So a palette keeps the app's own page (a navy or mid blue one too) and the red suits it;
  - a theme's `accent` is drawn on a device's own page in a scheme the theme gives no palette for (or one whose palette Relaid
    drops), so there it reaches 3:1 against that page: `#f6f7f9` and `#ffffff` in the light scheme, `#0f1114` and `#181b20` in the
    dark one; where it does not, Relaid ignores it and a device draws its own. A palette that takes the theme's accent was checked
    with it and keeps it;
  - an accent near Relaid's red in hue (within 30 degrees of `#c63b3b`'s, unless nearly grey), and a
    palette on which its own scheme's first red (`#c63b3b` for `light`, `#ff6b6b` for `dark`) does not
    reach 3:1 against background or surface, need pack format 3: an older Relaid ignores them.
- Packs contain no artwork. Tab icons and a control's icons come from Relaid's own generic set; an app's logos and
  pictures are never copied into a pack.

## Permissions

A pack can ask for more than shaping screens. It lists that in `pack.json` as `permissions`, the
index shows it, and Relaid tells the owner before installing ("Asks to: ..."). The owner grants it by
installing on the host itself, or with the host PIN when installing from another phone. Relaid uses
a permission only for the app of a pack that declared it and was granted it.

| Permission | Meaning |
|---|---|
| `touch` | Touch the screen where the app refuses a tap Relaid sends it, where an action has `perform`, and where a list has `scroll: "drag"`; never on secure screens and only where the app's own window is on top. On the host, Relaid's touch is switched on only while such an app is in front |
| `pictures` | Show the parts the pack marks as `picture`, captured from the app's own window only (never the keyboard, notifications or another app) and stored nowhere, on the host or the phone. Never on secure screens or the lock screen. On the host, Relaid's capture is switched on only while such an app is in front |

## Fixtures: captured screens and what the pack makes of them

A pack may keep captured screens of its app in `packs/<app>/<view>/fixtures/`, as the Relaid host reads
them. With the app shared and in front on a host, save one with
`adb shell dumpsys activity service relaid.host/.RelaidAccessibilityService tree | sed -n '/<snapshot/,/<\/snapshot>/p' > packs/<app>/<view>/fixtures/<name>.xml`. Next to them, `expect.json` says what the pack must make of each: which screen applies (`screen`), `secure`,
`title`, `actions`, `options`, `tabs`, `slides`, `gestures` (the controls Relaid swipes), `fields` (label to keyboard),
`keypad`, `progress`, `hero`, `avatars`, `headings`, `sizes` (label to the step the app draws it at: small, body,
large, larger or largest, `body` for none; only texts, headings and the screen's title), `rows` (every row of parts the app
draws side by side, in reading order: a list of its cells, each a label, or a list for a stack of parts one above the other,
which may hold a row; `[]` for none; more than 4 cells only where all of them are fit), `shares` (a cell's label to its share
of its row, 2 to 4, or 0 for a fit cell, which takes only its own width, where it is not 1; a stack's by its first part),
`align` (label to where it sits along its line: `start`, `center` or `end`; the screen's title's label for where the title sits;
a fit cell's label for where its row sits), `places` (the screen's title's label to where it stands: `bar`, or `page` where the
app draws it in its page rather than in its top bar; a control's label to where it sits: `top` in the top bar, `bottom` in the
bar along the bottom, or `back` for the app's own way back at the bar's start, which a device presses with its own back; one at
most), `tiles` (a control's label to the shape of the card the app draws it as, large on its own line: its width and height in
hundredths of the window's width, 1 to 100 wide and 1 to 200 tall; null for a control drawn as no tile, a row of a list), `widths` (a part's label to how wide the app draws it on its
line outside rows: `fit` at its own width, `full` across it, `same` at one width with the buttons the app stacks right under or over
it at that width, `none` as a device draws it), `tones` (a control's label to the tone it is
drawn in: `primary`, `secondary`, `muted`, `destructive`, or `none`), `pad` (the keypad's 12 places as the app lays out its own
pad, each the label of the key or of the app's part there, null for an empty one; null for a keypad laid out in Relaid's own
order), `entry` (the code entry's name, null for none), `values` (a part's label to the value it shows under its name: a field's
text, how far along its range a meter or a slider is (1 of 3, 40%), a row's second line; null for none), `phones` (a control's label
to the reason it needs the phone itself for, one of the `phone` reasons above, or `none`), `phone` (the screen's own reason, null for
none), `icons` (a control's label to the icon of Relaid's drawn beside its words, or `none`), `looks` (a control's label to the look it
is drawn in, `link` or `none`), `boxes` (a part's label to the box it
is drawn in, `card` or `note`, or `none`), `page` (the page the screen is drawn on, `accent`, or null for the theme's own), and labels
it `shows` or `hides`. Rows, shares, aligns, places, tiles,
widths and a keypad's places are measured from the app's own boxes (and from where it draws a text's words, line by line, which a host
writes as a node's `drawn-lines` for a text whose box is wider than its words: keep it in a capture), never set by a pack; with `rows` or `shares`, the screen's rows and shares must be exactly those. Relaid's tests run every pack's fixtures through
its real pipeline, so a change to Relaid or to a pack that breaks a screen shows up before anyone
installs it. Relaid itself knows no app; this is where that knowledge lives.

Before committing a capture, replace every personal detail in it: names of people, phone numbers,
amounts and messages from real activity, account names. Use placeholders such as "Contact One".
Keep the app's own words and small counts (a badge's "3"): the plain reading depends on them.
Once pushed, a capture is in the history for good.

## Changing or adding a pack

1. Edit `packs/<app>/<view>/view.json`. If it changed, raise `version` in `pack.json`. Add or update a
   fixture for the screens you changed.
2. Run `python3 tools/check.py --write`. It checks every pack and rewrites `index.json`.
3. Open a pull request. The same check runs on it.

Never put personal data in a view: no names, phone numbers or account details, only the app's
own labels.
