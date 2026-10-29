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

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.galenframework.api.Galen;
import com.galenframework.config.GalenConfig;
import com.galenframework.config.GalenProperty;
import com.galenframework.reports.GalenTestInfo;
import com.galenframework.reports.HtmlReportBuilder;
import com.galenframework.reports.model.LayoutReport;
import com.galenframework.speclang2.pagespec.SectionFilter;
import com.galenframework.validation.ValidationResult;
import org.openqa.selenium.WebDriver;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileDescriptor;
import java.io.FileOutputStream;
import java.io.InputStreamReader;
import java.io.PrintStream;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Date;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Properties;

/**
 * Entry point used by the Python robotframework-galenframework package.
 * <p>
 * Server mode (used by the library): {@code java -jar galen-robot-bridge.jar --server}<br>
 * Reads one JSON request per line from stdin and writes one JSON response per line to stdout.
 * Everything else Galen or Selenium prints is redirected to stderr. The process ends when stdin closes.
 * <p>
 * Single shot mode: {@code java -jar galen-robot-bridge.jar request.json result.json}
 * <p>
 * Commands: {@code checkLayout}, {@code capture}, {@code compare}, {@code ping}.
 */
public class GalenBridge {

    public static class Request {
        public String command = "checkLayout";
        public String executorUrl;
        public String sessionId;

        // checkLayout
        public String specPath;
        public List<String> includedTags = new ArrayList<>();
        public List<String> excludedTags = new ArrayList<>();
        public Map<String, String> properties = new HashMap<>();
        public Map<String, Object> jsVariables = new HashMap<>();
        public String reportDir;
        public boolean reportOnlyOnFailure;
        public String title;

        // capture / compare
        public VisualComparison.LocatorDto locator;
        public String imagePath;
        public String outputDir;
        public int tolerance = 25;
        public int analyzeOffset;
        public boolean stretch;
        public boolean fullPage;
        public List<VisualComparison.LocatorDto> ignore = new ArrayList<>();
    }

    public static class Message {
        public String message;
        public String place;
        public boolean warning;

        public Message() {
        }

        Message(String message, String place, boolean warning) {
            this.message = message;
            this.place = place;
            this.warning = warning;
        }
    }

    public static class Result {
        public int errors;
        public int warnings;
        public List<Message> messages = new ArrayList<>();
        public String reportPath;
    }

    public static class Response {
        public boolean ok = true;
        public Object result;
        public String exception;
    }

    private static final ObjectMapper MAPPER = new ObjectMapper()
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);

    private final Map<String, WebDriver> drivers = new HashMap<>();

    public static void main(String[] args) throws Exception {
        if (args.length == 1 && "--server".equals(args[0])) {
            new GalenBridge().serve();
        } else if (args.length == 2) {
            System.exit(new GalenBridge().runOnce(new File(args[0]), new File(args[1])));
        } else {
            System.err.println("Usage: java -jar galen-robot-bridge.jar --server");
            System.err.println("       java -jar galen-robot-bridge.jar <request.json> <result.json>");
            System.exit(1);
        }
    }

    private void serve() throws Exception {
        PrintStream protocol = new PrintStream(new FileOutputStream(FileDescriptor.out), true, "UTF-8");
        System.setOut(System.err);

        BufferedReader in = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        String line;
        while ((line = in.readLine()) != null) {
            if (line.trim().isEmpty()) {
                continue;
            }
            Response response = new Response();
            try {
                response.result = handle(MAPPER.readValue(line, Request.class));
            } catch (Throwable ex) {
                response.ok = false;
                response.exception = stackTrace(ex);
            }
            protocol.println(MAPPER.writeValueAsString(response));
        }
    }

    private int runOnce(File requestFile, File resultFile) throws Exception {
        Response response = new Response();
        try {
            response.result = handle(MAPPER.readValue(requestFile, Request.class));
        } catch (Throwable ex) {
            response.ok = false;
            response.exception = stackTrace(ex);
        }
        MAPPER.writerWithDefaultPrettyPrinter().writeValue(resultFile, response);
        return response.ok ? 0 : 2;
    }

    Object handle(Request request) throws Exception {
        switch (request.command) {
            case "ping":
                return "pong";
            case "checkLayout":
                return checkLayout(request);
            case "capture":
                return new VisualComparison(driver(request), request.fullPage)
                        .capture(request.locator, new File(required(request.imagePath, "imagePath")));
            case "compare":
                return new VisualComparison(driver(request), request.fullPage)
                        .compare(request.locator, new File(required(request.imagePath, "imagePath")),
                                new File(required(request.outputDir, "outputDir")), request.tolerance,
                                request.analyzeOffset, request.stretch, request.ignore);
            default:
                throw new IllegalArgumentException("Unknown command: " + request.command);
        }
    }

    private WebDriver driver(Request request) throws Exception {
        required(request.executorUrl, "executorUrl");
        required(request.sessionId, "sessionId");
        String key = request.executorUrl + "|" + request.sessionId;
        WebDriver driver = drivers.get(key);
        if (driver == null) {
            driver = ExistingSessionDriver.attach(new URL(request.executorUrl), request.sessionId);
            drivers.put(key, driver);
        }
        return driver;
    }

    private Result checkLayout(Request request) throws Exception {
        required(request.specPath, "specPath");
        WebDriver driver = driver(request);
        GalenConfig.getConfig().setProperty(GalenProperty.SCREENSHOT_FULLPAGE, Boolean.toString(request.fullPage));

        SectionFilter sectionFilter = new SectionFilter(request.includedTags, request.excludedTags);
        Properties properties = new Properties();
        properties.putAll(request.properties);

        String title = request.title != null ? request.title : "Check layout " + request.specPath;
        GalenTestInfo testInfo = GalenTestInfo.fromString(title);
        testInfo.setStartedAt(new Date());

        LayoutReport layoutReport = Galen.checkLayout(driver, request.specPath, sectionFilter, properties,
                request.jsVariables != null ? request.jsVariables : new LinkedHashMap<String, Object>());
        testInfo.getReport().layout(layoutReport, title);
        testInfo.setEndedAt(new Date());

        Result result = new Result();
        result.errors = layoutReport.errors();
        result.warnings = layoutReport.warnings();
        collectMessages(layoutReport.getValidationErrorResults(), result.messages);

        boolean writeReport = request.reportDir != null && (!request.reportOnlyOnFailure || result.errors > 0);
        if (writeReport) {
            new HtmlReportBuilder().build(Collections.singletonList(testInfo), request.reportDir);
            result.reportPath = new File(request.reportDir, "report.html").getAbsolutePath();
        }
        return result;
    }

    private static void collectMessages(List<ValidationResult> validationResults, List<Message> messages) {
        if (validationResults == null) {
            return;
        }
        for (ValidationResult validationResult : validationResults) {
            if (validationResult.getError() != null && validationResult.getError().getMessages() != null) {
                String place = null;
                if (validationResult.getSpec() != null && validationResult.getSpec().getPlace() != null) {
                    place = validationResult.getSpec().getPlace().toPrettyString();
                }
                for (String errorMessage : validationResult.getError().getMessages()) {
                    messages.add(new Message(errorMessage, place, validationResult.getError().isOnlyWarn()));
                }
            }
            collectMessages(validationResult.getChildValidationResults(), messages);
        }
    }

    private static String required(String value, String name) {
        if (value == null) {
            throw new IllegalArgumentException(name + " is required");
        }
        return value;
    }

    private static String stackTrace(Throwable ex) {
        StringWriter writer = new StringWriter();
        ex.printStackTrace(new PrintWriter(writer));
        return writer.toString();
    }
}
