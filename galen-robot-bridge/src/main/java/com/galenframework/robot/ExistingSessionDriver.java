/*******************************************************************************
* Copyright 2026 Belfor-IT
*
* Licensed under the Apache License, Version 2.0 (the "License");
* you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
*
*   http://www.apache.org/licenses/LICENSE-2.0
*
* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS,
* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
* See the License for the specific language governing permissions and
* limitations under the License.
******************************************************************************/
package com.galenframework.robot;

import org.openqa.selenium.ImmutableCapabilities;
import org.openqa.selenium.remote.Command;
import org.openqa.selenium.remote.CommandExecutor;
import org.openqa.selenium.remote.DriverCommand;
import org.openqa.selenium.remote.ErrorCodes;
import org.openqa.selenium.remote.RemoteWebDriver;
import org.openqa.selenium.remote.Response;
import org.openqa.selenium.remote.codec.w3c.W3CHttpCommandCodec;
import org.openqa.selenium.remote.codec.w3c.W3CHttpResponseCodec;
import org.openqa.selenium.remote.http.HttpHandler;
import org.openqa.selenium.remote.http.HttpRequest;
import org.openqa.selenium.remote.http.HttpResponse;

import java.io.IOException;
import java.net.URL;
import java.util.Collections;

/**
 * A {@link RemoteWebDriver} that does not start a new browser, but attaches to a WebDriver session
 * that was already created by another client (for instance Python SeleniumLibrary in Robot Framework).
 * The session is never closed from here: the owner of the session is responsible for quitting it.
 */
public final class ExistingSessionDriver {

    private ExistingSessionDriver() {
    }

    public static RemoteWebDriver attach(URL executorUrl, String sessionId) {
        return new RemoteWebDriver(new ExistingSessionExecutor(executorUrl, sessionId), new ImmutableCapabilities());
    }

    /**
     * Speaks the W3C WebDriver protocol to the remote end, but answers the "new session" command itself
     * with the id of the existing session instead of creating a new browser.
     */
    private static final class ExistingSessionExecutor implements CommandExecutor {
        private final String sessionId;
        private final HttpHandler client;
        private final W3CHttpCommandCodec commandCodec = new W3CHttpCommandCodec();
        private final W3CHttpResponseCodec responseCodec = new W3CHttpResponseCodec();

        ExistingSessionExecutor(URL executorUrl, String sessionId) {
            this.sessionId = sessionId;
            this.client = new UrlConnectionHttpHandler(executorUrl);
        }

        @Override
        public Response execute(Command command) throws IOException {
            if (DriverCommand.NEW_SESSION.equals(command.getName())) {
                return success(Collections.<String, Object>emptyMap());
            }
            if (DriverCommand.QUIT.equals(command.getName())) {
                // the session belongs to the client that created it
                return success(null);
            }
            HttpRequest request = commandCodec.encode(command);
            HttpResponse httpResponse = client.execute(request);
            Response response = responseCodec.decode(httpResponse);
            if (response.getSessionId() == null) {
                response.setSessionId(sessionId);
            }
            return response;
        }

        private Response success(Object value) {
            Response response = new Response();
            response.setSessionId(sessionId);
            response.setState("success");
            response.setStatus(ErrorCodes.SUCCESS);
            response.setValue(value);
            return response;
        }
    }
}
