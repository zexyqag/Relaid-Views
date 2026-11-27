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
selectors, wins). Its `parts` are one list of rules: each says what the nodes its `select` matches
are, with `as`. A rule without `as` only gives a `label` to a part that shows no text of its own.
Without a view Relaid still shows the screen plain: the main list, the header and footer around it,
the title, icon buttons in the header as a menu, the bottom navigation as tabs. A view is for what
that plain reading gets wrong, or shows differently from how you want it, so write only the rules a
screen needs.

| Screen field | Meaning |
|---|---|
| `name` | Stable id: lowercase letters, digits and dashes. The owner can switch a screen off by it |
| `displayName` | What people see: one line, at most 60 characters |
| `when` | Selectors that must all match for the screen to apply |
| `activity` | Part of the window's activity name, where `when` cannot tell screens apart |
| `secure` | Mark the screen secure when the app gives no signal for it |
| `priority` | Breaks ties when several screens match |
| `parts` | The rules, in order |

| `as` | Meaning | Options |
|---|---|---|
| `hidden` | Left out: ads, decoration, duplicates | |
| `text` | Shown as text, never as a control (an app that offers a click on every message), with everything in it | |
| `heading` | Shown as a section heading (who wrote the messages below, a date), with everything in it never a control | |
| `picture` | Shown as a picture, captured live from the app's own window. Only a part with no text and no control in it. Needs the permission `pictures` | `label`: named until the picture arrives |
| (none) | A part with no text and no control in it gets this text | `label` |
| `title` | The screen's title | |
| `hero` | Shown large and centred (an amount): text, a heading or a field | |
| `list` | The main list | `scroll: "drag"`: Relaid drags it, for an app that ignores the scroll Relaid sends. Needs `touch` |
| `field` | An input | `label` where the app gives none; `keyboard`: `number`, `phone`, `email`, `text` |
| `action` | A control in the bottom bar | `label` where the app shows none; `tone`: `primary`, `secondary`, `muted`, `destructive`; `confirm: "slide"`: a deliberate slide, and the screen is secure; `perform`: `click`, `swipe-right`, `swipe-left`, `swipe-up`, `swipe-down` (Relaid swipes the control; needs `touch`) |
| `option` | A control in the menu | `label`, `tone` |
| `tab` | The app's bottom navigation, in rule order. A tab with nothing to press is the current one | `label` where the app shows none; `icon`: `home`, `list`, `people`, `person`, `wallet`, `card`, `search`, `settings`, `bell`, `chart`, `star`, `chat`, `grid` |
| `person` | A row about a person, shown with a round avatar of its own initials | |
| `row` | A list row the app builds from separately pressable parts (an avatar, a name, a status) with none of them the row: shown as one item, the first part its title, the rest its second line | `parts`: the nodes whose text it shows (default every text); `press`: the node whose control a press goes to |
| `pin` | The app's own "N of M entered" node: only the counts cross over, never digits. If the app reports no count, select the code field and give `total`: the phone counts the person's own key presses. A code field with visible text is never replaced | `label` (without one, the app's own words drawn right above it name it, if any, but never the screen's title), `total` (1 to 12) |
| `unread` | Where on this screen Relaid looks for what it cannot read (photos drawn in a view of their own, a map, a chart), to show as pictures, where the owner chose that for the app. A screen a view knows gets such pictures only inside its `unread` parts, and none without them; screens no view knows, anywhere. An `unread` part inside a pressable list row is that row's thumbnail (a photo, album art). It only narrows the owner's choice, so it needs no permission. Pack format 2 | |

`title`, `hero`, `list` and `pin` appear at most once per screen.

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
  unlabelled button, but it cannot rename one.
- A view can add friction (`confirm: "slide"`, `secure`) but never remove it, and what one installed
  view of an app adds holds in all its views.
- On a secure screen nothing can be hidden or reshaped: `hidden`, `text`, `heading`, `picture`, `row`
  and bare labels are ignored there, and Relaid never touches or captures. Relaid marks a screen
  secure when it has a password field, a PIN pad, or a control that asks for a swipe or that a pack
  declares a slide, whatever the pack says otherwise; `secure` can mark more screens, never fewer.
- The skin applies to the whole screen by role, never to one control, and Relaid ignores any part
  that breaks these rules:
  - colours are `#RRGGBB`;
  - an accent stays more than 30 degrees of hue from Relaid's destructive red (unless nearly grey),
    and destructive actions always keep Relaid's own red;
  - a palette has `background`, `surface`, `text` and `muted`, and an accent (its own or the
    theme's); text and muted text reach 4.5:1 against background and surface, the accent and the
    destructive red reach 3:1, and `onAccent` (text on accent buttons, optional) reaches 3:1 against
    the accent.
- Packs contain no artwork. Tab icons come from Relaid's own generic set; an app's logos and pictures
  are never copied into a pack.

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
`align` (label to where it sits along its line: `start`, `center` or `end`; the screen's title's label for where the title sits),
`places` (the screen's title's label to where it stands: `bar`, or `page` where the app draws it in its page rather than in its
top bar), `pad` (the keypad's 12 places as the app lays out its own pad, each the label of the key or of the app's part there,
null for an empty one; null for a keypad laid out in Relaid's own order), `entry` (the code entry's name, null for none), and
labels it `shows` or `hides`. Rows, shares, aligns, places and a keypad's places are measured from the app's own boxes, never
set by a pack; with `rows` or `shares`, the screen's rows and shares must be exactly those. Relaid's tests run every pack's fixtures through
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
