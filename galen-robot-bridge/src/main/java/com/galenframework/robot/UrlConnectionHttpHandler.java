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

import org.openqa.selenium.remote.http.Contents;
import org.openqa.selenium.remote.http.HttpHandler;
import org.openqa.selenium.remote.http.HttpMethod;
import org.openqa.selenium.remote.http.HttpRequest;
import org.openqa.selenium.remote.http.HttpResponse;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.UncheckedIOException;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.List;
import java.util.Map;

/**
 * Sends WebDriver requests with plain blocking {@link HttpURLConnection}s.
 *
 * Selenium's default client is built on {@code java.net.http.HttpClient}, which needs a NIO selector.
 * On some Windows machines the JDK cannot create the selector's internal pipe ("Unable to establish
 * loopback connection"), so the bridge does not depend on it.
 */
final class UrlConnectionHttpHandler implements HttpHandler {
    private static final int CONNECT_TIMEOUT_MILLIS = 10_000;
    private static final int READ_TIMEOUT_MILLIS = 180_000;

    private final String baseUrl;

    UrlConnectionHttpHandler(URL baseUrl) {
        String url = baseUrl.toString();
        this.baseUrl = url.endsWith("/") ? url.substring(0, url.length() - 1) : url;
    }

    @Override
    public HttpResponse execute(HttpRequest request) {
        try {
            return send(request);
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    private HttpResponse send(HttpRequest request) throws IOException {
        String url = baseUrl + request.getUri();
        String query = request.getQueryString();
        if (query != null && !query.isEmpty()) {
            url += "?" + query;
        }

        // connections are not disconnected, so that the JDK can keep them alive for the next command
        HttpURLConnection connection = (HttpURLConnection) new URL(url).openConnection();
        connection.setConnectTimeout(CONNECT_TIMEOUT_MILLIS);
        connection.setReadTimeout(READ_TIMEOUT_MILLIS);
        connection.setRequestMethod(request.getMethod().name());
        request.forEachHeader(connection::addRequestProperty);

        if (request.getMethod() == HttpMethod.POST || request.getMethod() == HttpMethod.PUT) {
            byte[] body = Contents.bytes(request.getContent());
            connection.setDoOutput(true);
            connection.setFixedLengthStreamingMode(body.length);
            try (OutputStream out = connection.getOutputStream()) {
                out.write(body);
            }
        }

        HttpResponse response = new HttpResponse();
        int status = connection.getResponseCode();
        response.setStatus(status);
        for (Map.Entry<String, List<String>> header : connection.getHeaderFields().entrySet()) {
            if (header.getKey() != null) {
                for (String value : header.getValue()) {
                    response.addHeader(header.getKey(), value);
                }
            }
        }
        InputStream in = status >= 400 ? connection.getErrorStream() : connection.getInputStream();
        response.setContent(Contents.bytes(in == null ? new byte[0] : readAllAndClose(in)));
        return response;
    }

    private static byte[] readAllAndClose(InputStream in) throws IOException {
        try (InputStream stream = in) {
            return stream.readAllBytes();
        }
    }
}
