import Foundation

/// Names for the three bots — good old Swiss first names, the kind heard at a Jass table in a
/// Beiz, with a Swiss personality now and then. Presentation only: the engine never sees a
/// name. The same lists as `web/static/names.js`.
enum Names {
    private static let classic = [
        "Irma", "Elisabeth", "Rösli", "Vreni", "Trudi", "Heidi", "Margrit", "Erika", "Hedi",
        "Frieda", "Anneli", "Gritli", "Lisbeth", "Verena", "Klärli", "Martha", "Berta", "Hulda",
        "Rosmarie", "Theres", "Emmi", "Ida", "Agathe", "Dorli", "Elsbeth", "Greti", "Hanni",
        "Käthi", "Lotti", "Nelli", "Olga", "Ursula", "Vroni", "Zita", "Bethli", "Marili",
        "Annelies", "Josefine", "Mina", "Babette", "Frida", "Leni", "Resli", "Sophie", "Wilma",
        "Sepp", "Urs", "Hansruedi", "Ueli", "Köbi", "Fritz", "Heiri", "Godi", "Ruedi", "Walti",
        "Kari", "Werni", "Housi", "Alois", "Fridolin", "Gottfried", "Jakob", "Ernst", "Xaver",
        "Balz", "Chrigu", "Dölf", "Edi", "Fredi", "Gusti", "Hene", "Noldi", "Pius", "Röbi",
        "Sämi", "Toni", "Wisi", "Zeno", "Migg", "Beat", "Otto", "Willi", "Bruno", "Kurt", "Paul",
        "Vinzenz", "Emil", "Gody", "Seppli", "Hämpu", "Ruedl", "Fridu", "Res",
    ]

    private static let famous = [
        "DJ Bobo", "Albert Rösti", "Roger Federer", "Martina Hingis", "Bernhard Russi",
        "Vreni Schneider", "Pirmin Zurbriggen", "Lara Gut-Behrami", "Marco Odermatt",
        "Beni Thurnheer", "Emil Steinberger", "Ueli Maurer", "Doris Leuthard",
        "Simonetta Sommaruga", "Alain Berset", "Karin Keller-Sutter", "Guy Parmelin",
        "Viola Amherd", "Ignazio Cassis", "Simon Ammann", "Didier Cuche", "Dario Cologna",
        "Wendy Holdener", "Stan Wawrinka", "Belinda Bencic", "Michelle Hunziker", "Gölä",
        "Trauffer", "Francine Jordi", "Polo Hofer", "Stephan Eicher", "Kurt Aeschbacher",
        "Sven Epiney", "Ursula Andress", "Viktor Giacobbo", "Mike Müller", "Marco Rima",
        "Peach Weber", "Massimo Rocchi", "Lys Assia", "Nella Martinetti", "Beat Breu",
    ]

    /// Four names by seat; seat 0 is the player and stays empty (the UI says "You").
    static func deal() -> [String] {
        var picked: [String] = []
        while picked.count < 3 {
            let pool = Double.random(in: 0..<1) < 0.25 ? famous : classic
            if let name = pool.randomElement(), !picked.contains(name) { picked.append(name) }
        }
        return [""] + picked
    }
}
