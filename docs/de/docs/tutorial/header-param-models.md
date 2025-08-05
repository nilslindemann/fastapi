# <a id="header-parameter-models"></a> Header-Parameter-Modelle

Wenn Sie eine Gruppe verwandter **Header-Parameter** haben, können Sie ein **Pydantic-Modell** erstellen, um diese zu deklarieren.

Dadurch können Sie das **Modell an mehreren Stellen wiederverwenden** und auch Validierungen und Metadaten für alle Parameter gleichzeitig deklarieren. 😎

/// note | Hinweis

Dies wird seit FastAPI Version `0.115.0` unterstützt. 🤓

///

## <a id="header-parameters-with-a-pydantic-model"></a> Header-Parameter mit einem Pydantic-Modell

Deklarieren Sie die erforderlichen **Header-Parameter** in einem **Pydantic-Modell** und dann den Parameter als `Header`:

{* ../../docs_src/header_param_models/tutorial001_an_py310.py hl[9:14,18] *}

**FastAPI** wird die Daten für **jedes Feld** aus den **Headern** des Requests extrahieren und Ihnen das von Ihnen definierte Pydantic-Modell geben.

## <a id="check-the-docs"></a> Die Dokumentation überprüfen

Sie können die erforderlichen Header in der Dokumentationsoberfläche unter `/docs` sehen:

<div class="screenshot">
<img src="/img/tutorial/header-param-models/image01.png">
</div>

## <a id="forbid-extra-headers"></a> Zusätzliche Header verbieten

In einigen speziellen Anwendungsfällen (wahrscheinlich nicht sehr häufig) möchten Sie möglicherweise die **Header einschränken**, die Sie erhalten möchten.

Sie können Pydantics Modellkonfiguration verwenden, um `extra` Felder zu verbieten (`forbid`):

{* ../../docs_src/header_param_models/tutorial002_an_py310.py hl[10] *}

Wenn ein Client versucht, einige **zusätzliche Header** zu senden, erhält er eine **Error-Response**.

Zum Beispiel, wenn der Client versucht, einen `tool`-Header mit einem Wert von `plumbus` zu senden, erhält er eine **Error-Response**, die ihm mitteilt, dass der Header-Parameter `tool` nicht erlaubt ist:

```json
{
    "detail": [
        {
            "type": "extra_forbidden",
            "loc": ["header", "tool"],
            "msg": "Extra inputs are not permitted",
            "input": "plumbus",
        }
    ]
}
```

## <a id="disable-convert-underscores"></a> Automatische Umwandlung von Unterstrichen deaktivieren

Ähnlich wie bei regulären Header-Parametern werden bei der Verwendung von Unterstrichen in den Parameternamen diese **automatisch in Bindestriche umgewandelt**.

Wenn Sie beispielsweise einen Header-Parameter `save_data` im Code haben, wird der erwartete HTTP-Header `save-data` sein, und er wird auch so in der Dokumentation angezeigt.

Falls Sie aus irgendeinem Grund diese automatische Umwandlung deaktivieren müssen, können Sie dies auch für Pydantic-Modelle für Header-Parameter tun.

{* ../../docs_src/header_param_models/tutorial003_an_py310.py hl[19] *}

/// warning | Achtung

Bevor Sie `convert_underscores` auf `False` setzen, bedenken Sie, dass einige HTTP-Proxies und -Server die Verwendung von Headers mit Unterstrichen nicht zulassen.

///

## <a id="summary"></a> Zusammenfassung

Sie können **Pydantic-Modelle** verwenden, um **Header** in **FastAPI** zu deklarieren. 😎
