from django.db import migrations


def load_current_menu(apps, schema_editor):
    MenuCategory = apps.get_model("valdyti", "MenuCategory")
    MenuItem = apps.get_model("valdyti", "MenuItem")

    category_rows = [
        ("Sriubos", 10),
        ("Cepelinai", 20),
        ("Salotos", 30),
        ("Vištienos patiekalai", 40),
        ("Kiaulienos patiekalai", 50),
        ("Gruzdintos bulvytės", 60),
        ("Užkandžiai", 70),
        ("Lietiniai blyneliai", 80),
        ("Desertai", 90),
        ("Garnyrai", 100),
    ]
    categories = {}
    for name, sort_order in category_rows:
        categories[name], _ = MenuCategory.objects.get_or_create(name=name, defaults={"sort_order": sort_order})

    items = [
        ("Sriubos", "Dienos sriuba", "", "1.50", "2.00"),
        ("Sriubos", "Čili sriuba", "", "3.50", "5.00"),
        ("Sriubos", "Šaltibarščiai", "", "3.00", "4.50"),
        ("Sriubos", "Kaimiški šaltibarščiai", "Patiekiama su bulvių koše ir spirgučiais.", "3.50", "4.90"),
        ("Cepelinai", "Cepelinai su mėsa XL", "Padažas: baltas, grybų arba grietinės. Galima rinktis spirgučius.", "4.50", "6.50"),
        ("Salotos", "Vištienos salotos", "Aisbergo salotos, vyšniniai pomidoriukai, skrebučiai, vištiena, padažas.", "6.90", None),
        ("Salotos", "Graikiškos salotos", "Aisbergo salotos, agurkai, pomidorai, mėlynas svogūnas, alyvuogės, feta sūris, graikiški riešutai, alyvuogių aliejus.", "6.50", None),
        ("Salotos", "Krevečių salotos", "Aisbergo salotos, agurkai, paprika, porai, krevetės, majonezas.", "6.90", None),
        ("Salotos", "Krabų salotos", "Ryžiai, agurkai, paprika, konservuoti kukurūzai, krabų lazdelės, majonezas.", "5.90", None),
        ("Salotos", "Silkė su karštomis bulvėmis", "", "6.50", None),
        ("Vištienos patiekalai", "Firminis kepsnys „Klumpe“", "Vištienos filė įdaryta sūriu ir žolelių sviestu.", "8.90", None),
        ("Vištienos patiekalai", "Kepsnys „Eglė“", "Vištienos filė įdaryta pievagrybiais, graikiškais riešutais ir sūriu.", "9.50", None),
        ("Vištienos patiekalai", "Kepsnys „Gaspadinė“", "Vištienos filė įdaryta sūriu ir karštai rūkytu kumpeliu.", "8.90", None),
        ("Vištienos patiekalai", "Vištienos krūtinėlė grietinėlės padaže", "", "8.00", None),
        ("Vištienos patiekalai", "Vištienos krūtinėlė su sūriu", "", "8.50", None),
        ("Kiaulienos patiekalai", "„Vyrų“ kepsnys", "Kiaulienos nugarinė užkepta marinuotais svogūnais, sūriu ir kečupu.", "8.00", None),
        ("Kiaulienos patiekalai", "Kepsnys „Ąžuolas“", "Kiaulienos nugarinė įdaryta sūriu ir karštai rūkytu kumpeliu, morkomis ir sūriu.", "9.90", None),
        ("Kiaulienos patiekalai", "Kepsnys „Lokio kąsnis“", "Kiaulienos nugarinė įdaryta karštai rūkytu kumpeliu, morkomis ir sūriu.", "9.00", None),
        ("Kiaulienos patiekalai", "Kepsnys „Gaspadorius“", "Kiaulienos nugarinė užkepta karštai rūkytu kumpeliu, raugintais agurkais ir sūriu.", "9.00", None),
        ("Kiaulienos patiekalai", "„Lukių“ šonkauliukai", "", "9.90", None),
        ("Kiaulienos patiekalai", "Lietuviškas karbonadas su grybų padažu", "", "7.90", None),
        ("Kiaulienos patiekalai", "Lietuviškas karbonadas su sūriu", "", "8.50", None),
        ("Kiaulienos patiekalai", "Tikras šnicelis", "", "7.50", None),
        ("Kiaulienos patiekalai", "Naminiai kotletai su padažu", "", "4.00", "5.50"),
        ("Kiaulienos patiekalai", "Vengriškas guliašas", "", "4.50", "6.00"),
        ("Gruzdintos bulvytės", "Gruzdintos bulvytės su kečupu", "", "3.50", None),
        ("Gruzdintos bulvytės", "Gruzdintos bulvytės su daržovėmis", "", "4.50", None),
        ("Gruzdintos bulvytės", "Gruzdintos bulvytės su daržovėmis ir dešrelėmis", "", "5.90", None),
        ("Gruzdintos bulvytės", "„Aštuntokas“", "Gruzdintos bulvytės, dešrelė, agurkai, pomidorai, kečupas. Rekomenduojama vaikams.", "4.50", None),
        ("Užkandžiai", "Kepta duona su česnaku ir sūrio padažu", "", "5.90", None),
        ("Užkandžiai", "Tikrų vyrų užkandis", "Kepta duona, krevetės, svogūnų žiedai.", "10.00", None),
        ("Lietiniai blyneliai", "Lietiniai su dešrele ir sūriu", "", "5.50", None),
        ("Lietiniai blyneliai", "Lietiniai su bananais", "", "4.00", "5.50"),
        ("Lietiniai blyneliai", "Lietiniai su varške", "", "4.00", "5.50"),
        ("Lietiniai blyneliai", "Karališki lietiniai su bananais", "", "4.90", "6.90"),
        ("Lietiniai blyneliai", "Karališki lietiniai su varške", "", "4.90", "6.90"),
        ("Desertai", "Ledai su vaisiais", "", "4.00", None),
        ("Desertai", "Ledai su sirupu / šokoladu", "", "3.50", None),
        ("Desertai", "Pyragaitis", "", "5.00", None),
        ("Garnyrai", "Bulvių košė", "Pasirenkamas garnyras prie patiekalo.", None, None),
        ("Garnyrai", "Ryžiai", "Pasirenkamas garnyras prie patiekalo.", None, None),
        ("Garnyrai", "Gruzdintos bulvytės", "Pasirenkamas garnyras prie patiekalo (+1,00 €).", "1.00", None),
    ]
    for sort_order, (category_name, name, description, price, second_price) in enumerate(items, start=1):
        MenuItem.objects.get_or_create(
            category=categories[category_name],
            name=name,
            defaults={
                "description": description,
                "price": price,
                "second_price": second_price,
                "sort_order": sort_order,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("valdyti", "0002_menucategory_menuitem"),
    ]

    operations = [
        migrations.RunPython(load_current_menu, migrations.RunPython.noop),
    ]
