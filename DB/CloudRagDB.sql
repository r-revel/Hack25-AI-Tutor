IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = N'CloudRagDB')
BEGIN
    CREATE DATABASE CloudRagDB;
    PRINT 'База данных CloudRagDB создана.';
END
ELSE
BEGIN
    PRINT 'База данных CloudRagDB уже существует.';
END
GO
---------------------------------------------------------------------------------
USE CloudRagDB;
GO
---------------------------------------------------------------------------------
IF NOT EXISTS (SELECT * FROM sys.server_principals WHERE name = N'rag_user')
BEGIN
    CREATE LOGIN rag_user WITH PASSWORD = 'vt0u3fASAvsEgvVKYme1';
    PRINT 'Логин rag_user создан.';
END
ELSE
BEGIN
    PRINT 'Логин rag_user уже существует.';
END
GO
---------------------------------------------------------------------------------
IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = N'rag_user')
BEGIN
    CREATE USER rag_user FOR LOGIN rag_user;
    PRINT 'Пользователь rag_user создан в базе CloudRagDB.';
END
ELSE
BEGIN
    PRINT 'Пользователь rag_user уже существует в базе CloudRagDB.';
END
GO
---------------------------------------------------------------------------------
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = N'CloudDocs' AND type = N'U')
BEGIN
    CREATE TABLE CloudDocs (
        Id INT IDENTITY(1,1) PRIMARY KEY,
        Url NVARCHAR(512) NOT NULL,
        Title NVARCHAR(512) NOT NULL,
        Category NVARCHAR(255),
        Section NVARCHAR(255),
        Content NVARCHAR(MAX) NOT NULL
    );
    PRINT 'Таблица CloudDocs создана.';
END
ELSE
BEGIN
    PRINT 'Таблица CloudDocs уже существует.';
END
GO
---------------------------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE ON CloudDocs TO rag_user;
GRANT VIEW DEFINITION ON CloudDocs TO rag_user;
PRINT 'Права назначены пользователю rag_user.';
GO
