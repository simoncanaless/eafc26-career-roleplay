// Lanzador de EAFC 26 Roleplay: "EAFC Roleplay.exe".
//
// No es la app empaquetada: abre app.py con el Python del .venv que esta
// en la misma carpeta, sin ventana de consola. Asi el .exe nunca queda
// desactualizado: corre siempre el codigo que hay en la carpeta.
// Lo compila scripts\crear_acceso_directo.py con el csc.exe de Windows.

using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Windows.Forms;

static class Lanzador
{
    [STAThread]
    static int Main(string[] args)
    {
        string carpeta = AppDomain.CurrentDomain.BaseDirectory;
        string pythonw = Path.Combine(carpeta, ".venv", "Scripts", "pythonw.exe");
        string app = Path.Combine(carpeta, "app.py");

        if (!File.Exists(app) || !File.Exists(pythonw))
        {
            MessageBox.Show(
                "No encontre " + (File.Exists(app) ? "el entorno de Python (.venv)" : "app.py") +
                " en:\n" + carpeta + "\n\nEl .exe tiene que estar en la carpeta del proyecto, " +
                "junto a app.py. Para crear el entorno:\n\n" +
                "python -m venv .venv\n.venv\\Scripts\\python.exe -m pip install -r requirements.txt",
                "EAFC 26 Roleplay", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }

        string argumentos = "\"" + app + "\"" +
            string.Concat(args.Select(a => " \"" + a.Replace("\"", "\\\"") + "\""));
        var inicio = new ProcessStartInfo(pythonw, argumentos)
        {
            WorkingDirectory = carpeta,
            UseShellExecute = false,
        };
        Process.Start(inicio);
        return 0;
    }
}
