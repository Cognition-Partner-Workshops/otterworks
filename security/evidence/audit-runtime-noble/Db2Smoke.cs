using IBM.Data.Db2;

// A refused local-only connection proves the native provider loads and runs.
// This probe never contacts a real database.
try
{
    using var connection = new DB2Connection(
        "Server=127.0.0.1:1;Database=smoke;UID=smoke;PWD=smoke;Connect Timeout=1;");
    connection.Open();
    Console.Error.WriteLine("Unexpected successful connection");
    return 1;
}
catch (DB2Exception error)
{
    Console.WriteLine(error.Message);
    if (error.Message.Contains("SQL30081N") || error.Message.Contains("SQLSTATE=08001"))
    {
        Console.WriteLine("PASS: IBM Db2 native client loaded and refused the local test endpoint.");
        return 0;
    }
    return 1;
}
