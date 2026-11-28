// WinOcr.cs — uses Windows.Media.Ocr to locally recognize text in images (no gateway needed)
// Compile: csc /r:... /out:WinOcr.exe WinOcr.cs
// Usage: WinOcr.exe <imagePath> [langTag]
// Output: recognized text to stdout
using System;
using System.IO;
using System.Text;
using System.Threading.Tasks;
using Windows.Media.Ocr;
using Windows.Graphics.Imaging;
using Windows.Storage;
using Windows.Storage.Streams;
using Windows.Globalization;

public static class WinOcr
{
    public static async Task<string> Run(string path, string langTag)
    {
        var file = await StorageFile.GetFileFromPathAsync(path);
        using (var stream = await file.OpenAsync(FileAccessMode.Read))
        {
            var decoder = await BitmapDecoder.CreateAsync(stream);
            var bitmap = await decoder.GetSoftwareBitmapAsync();
            OcrEngine engine = null;
            if (!string.IsNullOrEmpty(langTag))
            {
                engine = OcrEngine.TryCreateFromLanguage(new Language(langTag));
            }
            if (engine == null)
            {
                engine = OcrEngine.TryCreateFromUserProfileLanguages();
            }
            if (engine == null) return "ERR: cannot create OCR engine";
            var result = await engine.RecognizeAsync(bitmap);
            var sb = new StringBuilder();
            foreach (var line in result.Lines) sb.AppendLine(line.Text);
            return sb.ToString();
        }
    }

    public static int Main(string[] args)
    {
        if (args.Length < 1)
        {
            Console.Error.WriteLine("Usage: WinOcr.exe <imagePath> [langTag]");
            return 2;
        }
        string path = args[0];
        string lang = args.Length > 1 ? args[1] : "";
        try
        {
            string text = Run(path, lang).GetAwaiter().GetResult();
            Console.Write(text);
            return 0;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine("ERR: " + ex.Message);
            return 1;
        }
    }
}
