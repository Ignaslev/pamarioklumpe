from django.db import migrations, models


# Read-only snapshot of KitchenForce's "Meniu peržiūra" on 2026-07-29.
# The two entries whose names begin with "testas" are deliberately omitted.
CURRENT_MENU = [
    ("Ind.", [(168, "Ind.", "0.30"), (195, "Įrank.", "0.00"), (290, "Atvežimas", "1.50"), (303, "Kavos ind.", "0.10")]),
    ("Cepelinai XXL", [(152, "Cepelinai", "6.50"), (159, "Cepelinai 0.5", "4.50"), (161, "Cepelinai 1.5", "10.00"), (306, "Cep. MIX", "6.50")]),
    ("Dienos p.", [(174, "Kotletai", "5.50"), (215, "Kotletai 0.5", "4.00"), (175, "Guliašas", "6.00"), (216, "Guliašas 0.5", "4.50"), (275, "Balandėliai", "6.00"), (276, "Balandėliai 0.5", "5.00"), (282, "V. B. Cep. Varšk.", "6.50"), (296, "Kotletai 1.5", "6.00")]),
    ("Sriubos", [(200, "Sriuba", "2.00"), (201, "Sriuba 0.5", "1.50"), (202, "Čili", "5.00"), (203, "Čili 0.5", "3.50"), (204, "Šaltibarščiai", "4.50"), (205, "Šaltibarščiai 0.5", "3.00"), (206, "Kaimiški šaltibarščiai", "4.90"), (207, "Kaimiški šaltibarščiai 0.5", "3.50")]),
    ("Vištienos patiekalai", [(28, "Klumpė", "8.90"), (29, "Eglė", "9.50"), (30, "Gaspadinė", "8.90"), (31, "Vištiena grietinėlės padaže", "8.00"), (32, "Vištiena su sūriu", "8.50"), (162, "Vištiena su grybų padažu", "8.00"), (183, "Višt. nat.", "7.50"), (281, "Eglė 0.5", "6.50")]),
    ("Kiaulienos patiekalai", [(33, "Vyrų kepsnys", "8.00"), (34, "Ąžuolas", "9.90"), (39, "Lokio kąsnis", "9.00"), (40, "Liuks šonkauliukai", "9.90"), (41, "Karbonadas su grybų pad.", "7.90"), (42, "Karbonadas su sūriu", "8.50"), (184, "Gaspadorius", "9.00"), (185, "Karbonadas nat.", "7.50"), (208, "Šnicelis", "7.50"), (299, "Karb. su baltu pad.", "7.90")]),
    ("Lietiniai blyneliai", [(297, "Liet. Be įd.", "4.00"), (313, "Lietiniai", "5.50"), (314, "Lietiniai 0.5", "4.00"), (315, "Karališki liet.", "6.90"), (316, "Karališki liet. 0.5", "4.90"), (318, "Lietiniai 1.5", "8.50"), (319, "Karališki liet. 1.5", "9.50")]),
    ("Salotos", [(15, "Cezario salotos", "6.90"), (16, "Graikiškos salotos", "6.50"), (17, "Krevečių salotos", "6.90"), (18, "Krabų salotos", "5.90"), (19, "Silkė su karštomis bulvėmis", "6.50")]),
    ("Bulvytės", [(20, "Bulvytės su kečupu", "3.50"), (21, "Bulvytės su daržovėmis", "4.50"), (22, "Fri d. d.", "5.90"), (23, "Aštuonkojis", "4.50"), (252, "Fri su dešrelėmis", "4.90")]),
    ("Užkandžiai", [(24, "Kepta duona su sūriu", "5.90"), (25, "Tikrų vyrų užkandis", "10.00"), (217, "Duona su česnaku", "5.00")]),
    ("Gėrimai", [(91, "Gira 0.5", "2.90"), (98, "Sultys", "2.00"), (101, "Vichy", "2.20"), (106, "Ledų kokteilis", "3.90"), (111, "Naminis limonadas", "3.90"), (114, "Arizona", "2.90"), (119, "Aisbergas", "4.00"), (124, "Gruziniškas limonadas", "3.50"), (164, "Coca-cola", "2.50"), (166, "Fanta", "2.50"), (167, "Sprite", "2.50"), (196, "Kef", "1.30"), (209, "Stalo vanduo 0.5l", "1.50"), (210, "Stalo vanduo 1l", "2.00"), (220, "Gira 0.3", "2.50"), (300, "Rožių limonadas", "2.00"), (309, "Šerbetas", "3.90")]),
    ("Kava", [(80, "Juoda kava", "2.20"), (81, "Balta kava", "2.50"), (82, "Cappuccino", "3.00"), (83, "Latte", "3.00"), (84, "Arbata", "1.50"), (88, "Klumpės kava", "3.50"), (176, "Espresso", "2.00"), (177, "Dvigubas espresso", "3.80"), (251, "Šalta kava", "3.50"), (321, "Dviguba juoda", "3.50")]),
    ("Alus", [(74, "Extra 0.5", "4.50"), (75, "Extra 0.3", "3.80"), (76, "Sidras", "4.50"), (77, "Grimbergen 0.5", "5.00"), (78, "Nealkoholinis", "4.00"), (79, "Grimbergen 0.25", "3.80"), (218, "Blanc", "3.80"), (219, "Blanc Nealk.", "3.50"), (301, "Nealk. sidras", "4.00")]),
    ("Alkoholis", [(138, "Vynas 100 ml", "3.50"), (140, "Putojantis vynas (0.7)", "18.00"), (145, "Alk. Kokteilis", "8.50"), (234, "Brendis 50 ml", "3.50"), (239, "Viskis", "3.50"), (240, "Degtinė", "3.00"), (241, "Tekila", "3.50"), (248, "Trauktinė", "3.00"), (295, "Šampaniukas mini", "6.00")]),
    ("Ledai", [(197, "Ledai su vaisiais", "4.00"), (227, "Ledai su sirupu", "3.50"), (228, "Ledai su šokoladu", "3.50"), (229, "Pyragaitis", "5.00"), (292, "Ledai", "3.50")]),
    ("Pad. atskirai", [(278, "Pad. atskirai", "0.00")]),
    ("LAISVA KAINA", [(336, "Individualus užsakymas", "10.00"), (337, "Individualus užsakymas", "40.00"), (338, "Individualus užsakymas", "45.00"), (339, "Individualus užsakymas", "25.00")]),
]


def load_kitchenforce_current_menu(apps, schema_editor):
    MenuCategory = apps.get_model("valdyti", "MenuCategory")
    MenuItem = apps.get_model("valdyti", "MenuItem")

    # The earlier migration was a visual starter menu. Keep it as history, but
    # remove it from the active management view rather than deleting records.
    MenuCategory.objects.update(is_active=False)
    MenuItem.objects.update(is_active=False)

    for category_order, (category_name, items) in enumerate(CURRENT_MENU, start=1):
        category, _ = MenuCategory.objects.get_or_create(
            name=category_name,
            defaults={"sort_order": category_order, "is_active": True},
        )
        category.parent = None
        category.sort_order = category_order
        category.is_active = True
        category.save(update_fields=("parent", "sort_order", "is_active"))

        for item_order, (kitchenforce_id, name, price) in enumerate(items, start=1):
            item = MenuItem.objects.filter(kitchenforce_id=kitchenforce_id).first()
            if item is None:
                # Reuse an unlinked starter row when its category and name
                # already match, preserving any useful hand-written description.
                item = MenuItem.objects.filter(
                    kitchenforce_id__isnull=True,
                    category=category,
                    name=name,
                ).first()

            if item is None:
                MenuItem.objects.create(
                    kitchenforce_id=kitchenforce_id,
                    category=category,
                    name=name,
                    price=price,
                    second_price=None,
                    sort_order=item_order,
                    is_active=True,
                )
                continue

            item.kitchenforce_id = kitchenforce_id
            item.category = category
            item.price = price
            item.second_price = None
            item.sort_order = item_order
            item.is_active = True
            item.save(update_fields=(
                "kitchenforce_id", "category", "price", "second_price",
                "sort_order", "is_active",
            ))


class Migration(migrations.Migration):
    dependencies = [
        ("valdyti", "0004_invoice_invoiceline"),
    ]

    operations = [
        migrations.AddField(
            model_name="menuitem",
            name="kitchenforce_id",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Šio įrašo identifikatorius KitchenForce sistemoje.",
                null=True,
                unique=True,
                verbose_name="KitchenForce ID",
            ),
        ),
        migrations.RunPython(load_kitchenforce_current_menu, migrations.RunPython.noop),
    ]
