# <a id="form-models"></a> Formularmodelle

Sie können **Pydantic-Modelle** verwenden, um **Formularfelder** in FastAPI zu deklarieren.

/// info | Info

Um Formulare zu verwenden, installieren Sie zuerst <a href="https://github.com/Kludex/python-multipart" class="external-link" target="_blank">`python-multipart`</a>.

Stellen Sie sicher, dass Sie eine [virtuelle Umgebung](../virtual-environments.md){.internal-link target=_blank} erstellen, sie aktivieren und es dann installieren, zum Beispiel:

```console
$ pip install python-multipart
```

///

/// note | Hinweis

Dies wird seit FastAPI Version `0.113.0` unterstützt. 🤓

///

## <a id="pydantic-models-for-forms"></a> Pydantic-Modelle für Formulare

Sie müssen nur ein **Pydantic-Modell** mit den Feldern deklarieren, die Sie als **Formularfelder** erhalten möchten, und dann den Parameter als `Form` deklarieren:

{* ../../docs_src/request_form_models/tutorial001_an_py39.py hl[9:11,15] *}

**FastAPI** wird die Daten für **jedes Feld** aus den **Formulardaten** in der Anfrage **extrahieren** und Ihnen das von Ihnen definierte Pydantic-Modell übergeben.

## <a id="check-the-docs"></a> Die Dokumentation überprüfen

Sie können dies in der Dokumentations-UI unter `/docs` überprüfen:

<div class="screenshot">
<img src="/img/tutorial/request-form-models/image01.png">
</div>

## <a id="forbid-extra-form-fields"></a> Zusätzliche Formularfelder verbieten

In einigen speziellen Anwendungsfällen (wahrscheinlich nicht sehr häufig) möchten Sie möglicherweise die Formularfelder auf nur diejenigen beschränken, die im Pydantic-Modell deklariert sind, und jegliche **zusätzlichen** Felder **verbieten**.

/// note | Hinweis

Dies wird seit FastAPI Version `0.114.0` unterstützt. 🤓

///

Sie können die Modellkonfiguration von Pydantic verwenden, um jegliche `extra` Felder zu `verbieten`:

{* ../../docs_src/request_form_models/tutorial002_an_py39.py hl[12] *}

Wenn ein Client versucht, einige zusätzliche Daten zu senden, erhält er eine **Error-Response**.

Zum Beispiel, wenn der Client versucht, folgende Formularfelder zu senden:

* `username`: `Rick`
* `password`: `Portal Gun`
* `extra`: `Mr. Poopybutthole`

erhält er eine Error-Response, die ihm mitteilt, dass das Feld `extra` nicht erlaubt ist:

```json
{
    "detail": [
        {
            "type": "extra_forbidden",
            "loc": ["body", "extra"],
            "msg": "Extra inputs are not permitted",
            "input": "Mr. Poopybutthole"
        }
    ]
}
```

## <a id="summary"></a> Zusammenfassung

Sie können Pydantic-Modelle verwenden, um Formularfelder in FastAPI zu deklarieren. 😎
