
var f = new File;
f.createForWriting("ln_constants.txt");

f.outTextLn("Inspecting LocalNormalization Constants & Enums");
f.outTextLn("=============================================");

// Iterate over the LocalNormalization constructor/prototype to find static constants
for (var key in LocalNormalization) {
    f.outTextLn("LocalNormalization." + key + " = " + LocalNormalization[key]);
}

for (var key in LocalNormalization.prototype) {
    try {
        var val = LocalNormalization.prototype[key];
        f.outTextLn("LocalNormalization.prototype." + key + " = " + val);
    } catch (e) { }
}

var ln = new LocalNormalization;
f.outTextLn("\nInstance Properties (Defaults):");
for (var key in ln) {
    if (typeof (ln[key]) !== "function")
        f.outTextLn(key + " = " + ln[key]);
}


f.close();
console.writeln("Constants written to ln_constants.txt");
