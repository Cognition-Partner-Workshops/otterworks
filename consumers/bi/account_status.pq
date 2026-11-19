let
    ExtractPath = Excel.CurrentWorkbook(){[Name = "AccountStatusExtract"]}[Content]{0}[Column1],
    Rows = Csv.Document(File.Contents(ExtractPath), [
        Delimiter = "|", Columns = {"BusinessDate", "AccountStatus", "CurrencyCode", "AccountCount"},
        Encoding = 65001
    ]),
    Typed = Table.TransformColumnTypes(Rows, {{"BusinessDate", type date},
        {"AccountStatus", type text}, {"CurrencyCode", type text}, {"AccountCount", Int64.Type}}, "en-US")
in
    Typed
