"""Промты картинок для карточек каталога (её задача 10.10: «промт под тему каталога для каждой подкатегории, для всех видов
товаров, в цветокоре сайта — не только дизайнерам, а всем, даже винную комнату»).

Одна позиция ITEMS = одна картинка: она же стоит во всех каталогах, где есть позиция.
Готовую картинку сохранить как site/img/katalog/_src/<ключ>.png (или .jpg/.webp), затем `python site/make_katalog_img.py`
и `python site/build.py` — картинка сама встанет в карточку. Страница с промтами и кнопками «Копировать» —
docs/промты_каталога.html (собирает make_katalog_img.py --prompts).
Палитра — как у слайдов (docs/промты_слайдов.md) и сайта (CLAUDE.md «ЦВЕТ»): тёплый беж, грейж, известняк, мрамор, латунь,
акценты бордовый и тёмно-синий; ЗЕЛЁНОГО НЕТ (поэтому зима и растений нет). Промты на английском.
"""

# общий блок для дома — та же усадьба, что на слайдах; лучше прикладывать слайд 1 (site/img/slides/s1.jpg)
HOME = (
    "Photorealistic interior and architectural photography, Architectural Digest editorial quality, shot on a full-frame "
    "camera. The same palatial neoclassical French-style private estate near Moscow as in the attached image: carved "
    "light limestone, boiserie panels, tall arched windows in thin black steel frames. Strict color palette of the brand: "
    "warm beige, greige, light limestone, white Calacatta marble, travertine, brushed brass, small accents of deep "
    "burgundy and deep navy blue velvet. No green color anywhere, no houseplants, no trees with leaves: early winter, "
    "blue hour dusk, light fresh snow outside, warm golden interior light. Horizontal frame, 4:3 aspect ratio, sharp "
    "details, calm uncluttered composition with the main subject in the center. One continuous photograph edge to edge: "
    "no borders, no collage, no split frame. No people, no text, no logos, no brand names, no watermarks."
)

# общий блок для техники и коммерции — предметная/инженерная съёмка в тех же цветах
TECH = (
    "Photorealistic premium product and architectural photography, clean editorial style of a high-end European "
    "engineering brand catalog, shot on a full-frame camera with soft diffused light. Strict color palette of the brand: "
    "warm beige and greige walls, light limestone and microcement surfaces, matte warm-white and graphite metal, brushed "
    "brass details, small accents of deep burgundy and deep navy blue. No green color anywhere, no plants, no bright "
    "saturated colors, no yellow safety stripes. Everything brand new, spotless, precisely installed. Horizontal frame, "
    "4:3 aspect ratio, sharp details, calm uncluttered composition with the main subject in the center. One continuous "
    "photograph edge to edge: no borders, no collage. No text, no labels, no logos, no brand names, no watermarks."
)

# ключ ITEMS → (общий блок, сцена). Люди — только где без них нельзя (мастер, инженер), лица не крупно.
PROMPTS = {
 # --- владельцу: прямые интересы ---
 "turnkey": (HOME, "Exterior, three-quarter view of the finished mansion at dusk from the snowy cour d'honneur: gravel "
   "forecourt with lanterns, grand entrance steps, every window glowing warm gold. A sense of a completed, perfect home "
   "ready for the owners to arrive."),
 "arch": (HOME, "Architect's study inside the estate: a large travertine table with an elegant hand-drawn facade "
   "elevation of the mansion on cream paper, a precise white architectural model of the house, brass drafting "
   "instruments, rolled drawings tied with burgundy ribbon. Tall arched window with snowy garden at dusk behind."),
 "build": (HOME, "The mansion under construction at the finishing stage on a clear winter morning: limestone facade "
   "almost complete, neat scaffolding wrapped in clean greige mesh on one wing, tidy site with stacked limestone "
   "blocks on pallets, fresh snow. Orderly and calm, no mud, no clutter, no cranes in the foreground."),
 "spa": (HOME, "Private home spa: indoor swimming pool in white Calacatta marble, softly lit water, limestone columns, "
   "a glass-walled hammam with marble benches visible in the background, beige loungers, folded burgundy towels, brass "
   "wall lights, arched windows to the snowy garden. Dry clear glass, no fog."),
 "cinema": (HOME, "Private home cinema: deep navy blue velvet acoustic wall panels, a row of wide reclining armchairs "
   "in beige leather, burgundy velvet cushions, a large screen showing a soft abstract warm glow (no recognizable "
   "image), hidden brass step lights, coffered dark ceiling with tiny star lights. Intimate and quiet."),
 "wine": (HOME, "Wine cellar and tasting room in the estate: vaulted limestone ceiling, floor-to-ceiling racks of dark "
   "oak and brushed brass holding hundreds of bottles, a glass-walled climate-controlled wine wall glowing softly, a "
   "travertine tasting table with two crystal glasses of red wine and a decanter, burgundy velvet chairs, warm candle-like "
   "light. Cool calm atmosphere."),
 "winter_garden": (HOME, "Glass orangery gallery attached to the mansion: floor-to-ceiling arched glazing in black "
   "steel frames, travertine floor, beige linen sofas, a brass and marble coffee table, lanterns. Outside: snowy formal "
   "garden at blue hour. Inside warm and dry, glass perfectly clear, no condensation. No plants inside."),
 "pergola": (HOME, "Stone terrace of the mansion in early winter dusk: a modern aluminium bioclimatic pergola in "
   "graphite with louvered roof closed, integrated warm linear lighting and infrared heaters glowing softly, outdoor "
   "lounge sofa in greige fabric with burgundy throws, travertine floor, light snow on the balustrade beyond."),
 "interior_full": (HOME, "Grand living room fully furnished as one design: sofas in beige boucle, one deep navy velvet "
   "armchair, Calacatta marble fireplace, floor-to-ceiling silk-linen curtains with brass rods, large silk rug, crystal "
   "and brass chandelier, art books on a travertine table. Complete, harmonious, ready to live in."),
 "furniture_home": (HOME, "Master bedroom with European luxury furniture: upholstered bed with tall greige headboard, "
   "burgundy velvet bench at its foot, walnut bedside tables with brass handles, alabaster lamps, boiserie walls, soft "
   "rug, curtains drawn halfway on a snowy dusk view."),
 "furniture_out": (HOME, "Covered loggia of the mansion facing the snowy garden at dusk: teak and graphite aluminium "
   "outdoor lounge furniture with weatherproof greige cushions and burgundy accent pillows, travertine floor, brass "
   "lanterns, limestone columns. Light snow beyond the columns."),
 "lights": (HOME, "Close view of a statement chandelier made of hand-blown clear glass and white porcelain elements "
   "with brushed brass frame, glowing warm, hanging in a double-height hall with a coffered ceiling; a pair of matching "
   "porcelain wall sconces on limestone walls. The light fixture is the hero of the frame."),
 "curtains": (HOME, "Tall arched window in a drawing room dressed with floor-to-ceiling curtains in heavy beige "
   "silk-linen with perfect pleats, sheer voile layer, deep burgundy velvet tiebacks, brushed brass curtain rod with "
   "finials. Soft dusk light filtering through the voile, snowy garden outside."),
 "carpets": (HOME, "Large hand-knotted silk and wool rug in a soft greige, ivory and muted navy pattern with a thin "
   "burgundy border, laid on a herringbone oak floor in a living room, beige boucle sofa edge and marble table leg "
   "visible. View from slightly above showing the rug texture."),
 "home_textile": (HOME, "Beautifully made bed in the master suite: crisp ivory linen sheets, quilted greige silk "
   "bedspread, burgundy velvet cushions and a navy cashmere throw, sheer canopy fabric draped from a brass frame. "
   "Close, soft, tactile textures."),
 "garden": (HOME, "The estate's formal garden at blue hour in early winter: snow-covered parterre, gravel paths swept "
   "clean, warm uplighting on bare sculpted trees and stone statues, a pavilion with an outdoor kitchen and fireplace "
   "glowing, lanterns along the paths, the lit mansion in the background."),
 "smart_home": (HOME, "Evening in the living room: a slim brass and glass wall control panel with soft glowing icons "
   "(no readable text) next to the doorway, motorised curtains half closed, warm dimmed cove lighting, a phone lying on "
   "a marble table with a blank softly glowing screen. Calm, effortless comfort."),

 # --- ассистенту: обслуживание, климат, отопление и вода ---
 "diag": (HOME, "Engineer in a navy work jacket checking the ventilation of the estate: a clean technical room with "
   "greige walls, a compact ventilation unit, the engineer holding a tablet with a blank glowing screen and an "
   "anemometer near a ceiling grille. Face not in focus, hands and instruments sharp."),
 "service_contract": (HOME, "Service visit at the estate: a neat navy service van parked on the snowy gravel forecourt "
   "at the side entrance in the morning, a technician in a navy jacket carrying a slim graphite tool case towards the "
   "service door. Discreet and calm. No text on the van."),
 "euro_service": (TECH, "Workbench in a clean service workshop with warm beige walls: a disassembled European "
   "ventilation unit part, a new spare part in a graphite box, precise tools laid out on a burgundy mat, brass "
   "measuring instruments. Order and expertise."),
 "ac": (HOME, "Bedroom ceiling with a fully hidden ducted air conditioner: only an elegant thin linear slot diffuser "
   "integrated into the plaster ceiling cornice, painted to match. Upholstered bed below, curtains, calm evening light. "
   "No wall-mounted indoor units anywhere."),
 "air_treat": (HOME, "Children's bedroom in soft ivory and greige: a minimal premium air purifier and humidifier in "
   "warm-white matte finish with a brass top ring standing near the bed, a soft barely visible mist, linen bedding, "
   "a navy wool toy elephant. Fresh and quiet."),
 "aesthetic": (TECH, "A sleek home ventilation unit with heat recovery in matte warm-white casing installed in a tidy "
   "technical room of a private house: neatly insulated round ducts in graphite, brass fittings, microcement floor, "
   "greige walls, soft daylight. Looks like premium home equipment, not industrial."),
 "boilers": (TECH, "Boiler room of a luxury private house: two wall-hung gas boilers in matte warm-white, perfectly "
   "aligned copper and graphite pipework with brass valves, a hot water cylinder, insulated pipes, microcement floor, "
   "greige walls, soft warm light. Clean like a showroom."),
 "water": (TECH, "Water treatment station in the technical room of a private house: a row of tall filter columns in "
   "graphite and warm-white, brass valves and gauges, neat pipework, a crystal glass of clear water on a stone shelf "
   "in the foreground. Greige walls."),
 "plumbing": (HOME, "Master bathroom in Calacatta marble: freestanding stone bathtub, brushed brass taps, a slim linear "
   "floor drain with brass grille in the walk-in shower, double travertine vanity, folded burgundy towels. Pristine and "
   "dry."),
 "sun": (HOME, "Panoramic glazed living room with motorised fabric roller blinds in greige half lowered over the tall "
   "windows, soft filtered low winter sun, linen sofa, marble floor, warm shadows. Light control as part of the "
   "interior."),

 # --- дизайнеру: отделка, текстиль, стекло ---
 "plaster": (HOME, "Close detail of a wall finished with Venetian decorative plaster in warm greige with a subtle silky "
   "sheen and depth, a brushed brass wall sconce casting soft light across the texture, a corner of a limestone "
   "console with a stack of plaster colour samples and a steel trowel."),
 "textile_walls": (HOME, "Study with walls upholstered in deep navy blue silk fabric in soft panels framed by thin "
   "brushed brass mouldings, a walnut desk, burgundy leather chair, warm desk lamp. Close enough to see the fabric "
   "texture and seams."),
 "stone": (HOME, "Staircase hall clad in book-matched Calacatta marble slabs with dramatic veining, a travertine floor, "
   "brass handrail, a few loose marble and travertine sample slabs leaning against the wall. Natural stone as the hero."),
 "floors": (HOME, "Grand hallway floor in oak parquet laid in a Versailles pattern, transitioning to a marble inlay "
   "border at the doorway, low warm sunlight raking across the surface to show the texture, boiserie walls."),
 "fabrics": (HOME, "Decorator's table in the estate: neatly fanned fabric sample books and swatches — silk, linen, "
   "velvet, boucle in ivory, greige, deep burgundy and navy — with brass scissors and a tape measure on travertine."),
 "partitions": (HOME, "Sliding glass partition with thin black steel frames dividing a living room and a library, clear "
   "and reeded glass panels, brass handles, view through to bookshelves and a navy velvet armchair."),
 "glass_rail": (HOME, "Sweeping limestone staircase in a double-height hall with a frameless clear glass balustrade "
   "and a slim brushed brass handrail, crystal chandelier above, marble floor below."),
 "glass_facade": (HOME, "Garden facade of the mansion seen from the snowy terrace at dusk: floor-to-ceiling panoramic "
   "glazing in thin black steel frames across two storeys, warm lit interior visible through perfectly clear glass, "
   "limestone around the openings."),

 # --- монтажникам и коммерции: техника Frivent и инженерия ---
 "klimabox": (TECH, "Large modular air handling unit with heat recovery in matte warm-white and graphite panels "
   "installed in a spacious clean plant room of a premium office building, neatly insulated rectangular ducts, brass "
   "inspection hatches, epoxy floor in greige."),
 "aquavent": (TECH, "Pool dehumidification unit in matte warm-white casing installed in the plant room next to an "
   "indoor pool, insulated ducts leading up; through a glass partition the marble pool hall is visible with perfectly "
   "clear dry windows."),
 "central_ac": (TECH, "Very large central air conditioning unit in matte warm-white panels in the plant room of a "
   "museum or luxury hotel, long precise row of sections, insulated ducts, soft overhead light, greige walls, polished "
   "concrete floor."),
 "dd": (TECH, "Spacious clean warehouse with high ceilings and greige walls: several compact air heating units in "
   "graphite mounted high on the walls with adjustable louvres, warm air direction suggested by soft light, neat "
   "shelving below, polished floor."),
 "automation": (TECH, "Open control cabinet for ventilation: graphite steel enclosure with neatly routed wires in "
   "navy and burgundy colors, rows of modules, a small touch controller with a blank glowing screen on the door, "
   "greige wall."),
 "radiators": (HOME, "Modern aluminium sectional radiator in warm-white under a tall arched window of a bedroom, "
   "neat chrome-free brass valves, linen curtains, snowy view outside. The radiator is clearly visible and elegant."),
 "convectors": (HOME, "Close view along floor-to-ceiling glazing: a built-in floor trench convector with a slim "
   "brushed brass linear grille set flush into a travertine floor, running along the glass, snowy garden outside, "
   "perfectly clear glass without condensation."),
 "duct_fans": (TECH, "Inline duct fans in graphite casing installed in a clean ceiling void of a premium restaurant "
   "building, round insulated ducts, brass clamps, neat cable trays, soft light."),
 "smoke": (TECH, "Smoke exhaust system of a modern public building: a large roof smoke exhaust fan in graphite on a "
   "clean roof at dusk, and a rectangular fire damper with a navy actuator on a duct in the foreground. Orderly and "
   "reliable."),
 "calc": (TECH, "Engineer's desk: printed HVAC drawings of a building on cream paper, a laptop with a blank screen, "
   "a calculator, brass pen, a small model of a ventilation unit, a cup of coffee. Warm desk light, greige wall."),
 "pnr": (TECH, "Commissioning of a ventilation unit: an engineer in a navy jacket measuring airflow with a hood "
   "instrument at a ceiling grille in a finished premium interior, a second instrument with a blank display in the "
   "foreground. Face not in focus."),

 # --- застройщику ---
 "typical": (HOME, "Aerial dusk view of a gated cottage community near Moscow in early winter: a row of similar "
   "premium limestone mansions with graphite roofs, identical neat layout, warm lit windows, snowy lawns, lanterns "
   "along the private road. No green."),
 "install": (TECH, "Our installation team at work in a house at the engineering stage: neatly suspended insulated "
   "ducts and pipework under the concrete ceiling, workers in navy uniforms on a platform, tidy materials on pallets. "
   "Faces not in focus."),
 "resident_service": (HOME, "Gated community gatehouse in limestone with a wrought-iron gate at winter dusk, a navy "
   "service van entering, lanterns lit, snowy road, mansions in the background. No text on the van."),

 # --- коммерции ---
 "ice": (TECH, "Indoor ice arena with perfectly clear air: fresh smooth ice, greige stands with navy seats, large "
   "dehumidification ducts running under the roof trusses, soft white light. No fog, no players."),
 "commercial_calc": (TECH, "Upscale restaurant dining hall in greige and burgundy, empty before opening: elegant "
   "linear ceiling diffusers integrated into the ceiling, an engineer's tablet with a blank screen and drawings lying "
   "on a marble table in the foreground."),
}
