package rules

// VerbDataVersion identifies this verb data set. Increase it when the tables
// below change, because the fixtures and the measured precision refer to a
// specific version.
const VerbDataVersion = "1.0.0"

// beForms are the forms of the verb "to be".
var beForms = map[string]bool{
	"am": true, "is": true, "are": true, "was": true, "were": true,
	"be": true, "been": true, "being": true,
}

// perfectAux are the auxiliaries that make the perfect tenses.
var perfectAux = map[string]bool{"has": true, "have": true, "had": true}

// interrupters are the words that can come between an auxiliary and its
// participle. Any word that ends with "ly" is also accepted.
var interrupters = map[string]bool{
	"not": true, "never": true, "also": true, "already": true,
	"still": true, "always": true, "just": true, "only": true,
	"now": true, "then": true, "again": true, "ever": true,
	"yet": true, "even": true, "often": true, "soon": true,
}

// irregularParticiples are the past participles that do not end with "ed".
var irregularParticiples = map[string]bool{
	"been": true, "begun": true, "bent": true, "bound": true, "broken": true,
	"brought": true, "built": true, "bought": true, "caught": true,
	"chosen": true, "come": true, "cut": true, "done": true, "drawn": true,
	"driven": true, "eaten": true, "fallen": true, "felt": true,
	"fed": true, "flown": true, "forgotten": true, "found": true,
	"given": true, "gone": true, "got": true, "gotten": true, "grown": true,
	"held": true, "hidden": true, "hit": true, "kept": true, "known": true,
	"laid": true, "led": true, "left": true, "lent": true, "lost": true,
	"made": true, "meant": true, "met": true, "paid": true, "put": true,
	"read": true, "rebuilt": true, "rewritten": true, "run": true,
	"said": true, "seen": true, "sent": true, "set": true, "shown": true,
	"shut": true, "sold": true, "spoken": true, "spent": true, "split": true,
	"stolen": true, "struck": true, "sunk": true, "taken": true,
	"taught": true, "thought": true, "thrown": true, "told": true,
	"torn": true, "understood": true, "withdrawn": true, "won": true,
	"worn": true, "written": true,
}

// adjectivalParticiples are the past participles that usually work as
// adjectives after "to be". The passive rule does not report them, unless a
// "by" agent follows.
var adjectivalParticiples = map[string]bool{
	"allowed": true, "authorized": true, "based": true, "called": true,
	"closed": true, "complete": true, "connected": true, "configured": true,
	"deprecated": true, "disabled": true, "disconnected": true,
	"documented": true, "enabled": true, "expected": true, "finished": true,
	"gone": true, "installed": true, "intended": true, "involved": true,
	"known": true, "limited": true, "located": true, "locked": true,
	"named": true, "needed": true, "open": true, "prepared": true,
	"protected": true, "ready": true, "related": true, "required": true,
	"reserved": true, "restricted": true, "supported": true, "unlocked": true,
	"used": true,
}

// adjectivalIng are the "-ing" words that work as adjectives or nouns after
// "to be". The progressive rule does not report them.
var adjectivalIng = map[string]bool{
	"anything": true, "challenging": true, "confusing": true,
	"corresponding": true, "during": true, "everything": true,
	"existing": true, "following": true, "interesting": true,
	"leading": true, "meaning": true, "misleading": true, "missing": true,
	"morning": true, "nothing": true, "outstanding": true, "pending": true,
	"promising": true, "remaining": true, "something": true, "spring": true,
	"string": true, "surprising": true, "thing": true, "willing": true,
	"engineering": true,
}

// verbForms lists all inflections of the base verbs that the phrasal-verb
// table uses.
var verbForms = map[string][]string{
	"back":   {"back", "backs", "backed", "backing"},
	"break":  {"break", "breaks", "broke", "broken", "breaking"},
	"bring":  {"bring", "brings", "brought", "bringing"},
	"carry":  {"carry", "carries", "carried", "carrying"},
	"check":  {"check", "checks", "checked", "checking"},
	"come":   {"come", "comes", "came", "coming"},
	"figure": {"figure", "figures", "figured", "figuring"},
	"fill":   {"fill", "fills", "filled", "filling"},
	"find":   {"find", "finds", "found", "finding"},
	"get":    {"get", "gets", "got", "gotten", "getting"},
	"go":     {"go", "goes", "went", "gone", "going"},
	"hold":   {"hold", "holds", "held", "holding"},
	"keep":   {"keep", "keeps", "kept", "keeping"},
	"make":   {"make", "makes", "made", "making"},
	"pick":   {"pick", "picks", "picked", "picking"},
	"point":  {"point", "points", "pointed", "pointing"},
	"put":    {"put", "puts", "putting"},
	"set":    {"set", "sets", "setting"},
	"shut":   {"shut", "shuts", "shutting"},
	"take":   {"take", "takes", "took", "taken", "taking"},
	"turn":   {"turn", "turns", "turned", "turning"},
	"work":   {"work", "works", "worked", "working"},
}

// PhrasalVerb is one entry of the phrasal-verb table. Particle can hold more
// than one word, as in "get rid of".
type PhrasalVerb struct {
	Base       string
	Particle   []string
	Suggestion string
}

// phrasalVerbs holds the phrasal verbs that this version detects. The list is
// short on purpose: each entry must be a phrasal verb in almost all contexts.
var phrasalVerbs = []PhrasalVerb{
	{"back", []string{"up"}, "Write \"make a backup\"."},
	{"break", []string{"down"}, "Write \"stop\" or \"divide\"."},
	{"bring", []string{"up"}, "Write \"start\" or \"show\"."},
	{"carry", []string{"out"}, "Write \"do\" or \"obey\"."},
	{"check", []string{"out"}, "Write \"examine\"."},
	{"come", []string{"up", "with"}, "Write \"make\" or \"find\"."},
	{"figure", []string{"out"}, "Write \"calculate\" or \"find\"."},
	{"fill", []string{"out"}, "Write \"complete\"."},
	{"find", []string{"out"}, "Write \"find\" or \"learn\"."},
	{"get", []string{"rid", "of"}, "Write \"remove\"."},
	{"go", []string{"through"}, "Write \"examine\" or \"do\"."},
	{"hold", []string{"on"}, "Write \"wait\"."},
	{"keep", []string{"on"}, "Write \"continue\"."},
	{"make", []string{"up"}, "Write \"assemble\" or \"prepare\"."},
	{"pick", []string{"up"}, "Write \"lift\" or \"get\"."},
	{"point", []string{"out"}, "Write \"show\"."},
	{"put", []string{"on"}, "Write \"install\"."},
	{"set", []string{"up"}, "Write \"install\", \"prepare\", or \"adjust\"."},
	{"shut", []string{"down"}, "Write \"stop\"."},
	{"take", []string{"off"}, "Write \"remove\"."},
	{"take", []string{"out"}, "Write \"remove\"."},
	{"turn", []string{"off"}, "Write \"stop\" or \"de-energize\"."},
	{"turn", []string{"on"}, "Write \"start\" or \"energize\"."},
	{"work", []string{"out"}, "Write \"calculate\" or \"solve\"."},
}

// phrasalIndex maps a verb form to the entries that can start with it.
var phrasalIndex = buildPhrasalIndex()

func buildPhrasalIndex() map[string][]PhrasalVerb {
	index := map[string][]PhrasalVerb{}
	for _, pv := range phrasalVerbs {
		for _, form := range verbForms[pv.Base] {
			index[form] = append(index[form], pv)
		}
	}
	return index
}
