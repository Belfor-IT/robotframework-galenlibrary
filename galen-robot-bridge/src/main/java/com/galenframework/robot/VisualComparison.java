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

import com.galenframework.browser.SeleniumBrowser;
import com.galenframework.config.GalenConfig;
import com.galenframework.config.GalenProperty;
import com.galenframework.page.Page;
import com.galenframework.page.PageElement;
import com.galenframework.page.Rect;
import com.galenframework.rainbow4j.ComparisonOptions;
import com.galenframework.rainbow4j.ImageCompareResult;
import com.galenframework.rainbow4j.Rainbow4J;
import com.galenframework.specs.page.Locator;
import com.galenframework.page.selenium.WebPageElement;
import org.openqa.selenium.JavascriptExecutor;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;

import java.awt.BasicStroke;
import java.awt.Color;
import java.awt.Graphics2D;
import java.awt.Rectangle;
import java.awt.image.BufferedImage;
import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

/**
 * Screenshot based checks: capturing an element (or the viewport) as a baseline image and comparing
 * the current state of the page with that baseline. Uses Galen's own screenshot and element-area
 * logic and Rainbow4J for the comparison, so the results match Galen's {@code image} spec.
 *
 * Galen measures elements from the top of the document. A normal screenshot only shows the window,
 * so element areas are moved by the scroll position. An element that is (mostly) outside the window
 * is scrolled into view first; the original scroll position is restored afterwards.
 */
public class VisualComparison {

    public static final String VIEWPORT = "viewport";
    public static final String SCREEN = "screen";

    public static class LocatorDto {
        public String type;
        public String value;

        public LocatorDto() {
        }

        LocatorDto(String type, String value) {
            this.type = type;
            this.value = value;
        }
    }

    public static class CaptureResult {
        public String path;
        public int width;
        public int height;
    }

    public static class CompareResult {
        public boolean sizeMismatch;
        public int width;
        public int height;
        public int baselineWidth;
        public int baselineHeight;
        public double percentage;
        public long pixels;
        public int offsetX;
        public int offsetY;
        public String actualPath;
        public String heatmapPath;
        public String baselineCopyPath;
    }

    private final WebDriver driver;
    private final Page page;
    private final boolean fullPage;

    public VisualComparison(WebDriver driver, boolean fullPage) {
        this.driver = driver;
        this.fullPage = fullPage;
        this.page = new SeleniumBrowser(driver).getPage();
    }

    public CaptureResult capture(LocatorDto locator, File output) throws IOException {
        Shot shot = screenshot(locator, null);
        BufferedImage screenshot = shot.image;
        Rectangle area = shot.area;
        BufferedImage image = copy(screenshot.getSubimage(area.x, area.y, area.width, area.height));
        write(image, output);

        CaptureResult result = new CaptureResult();
        result.path = output.getAbsolutePath();
        result.width = image.getWidth();
        result.height = image.getHeight();
        return result;
    }

    public CompareResult compare(LocatorDto locator, File baseline, File outputDir, int tolerance,
                                 int analyzeOffset, boolean stretch, List<LocatorDto> ignore) throws IOException {
        Shot shot = screenshot(locator, ignore);
        BufferedImage screenshot = shot.image;
        Rectangle area = shot.area;
        BufferedImage actual = copy(screenshot.getSubimage(area.x, area.y, area.width, area.height));
        BufferedImage sample = Rainbow4J.loadImage(baseline.getAbsolutePath());

        outputDir.mkdirs();
        CompareResult result = new CompareResult();
        result.width = actual.getWidth();
        result.height = actual.getHeight();
        result.baselineWidth = sample.getWidth();
        result.baselineHeight = sample.getHeight();
        result.actualPath = write(actual, new File(outputDir, "actual.png"));
        result.baselineCopyPath = write(sample, new File(outputDir, "baseline.png"));

        if (!stretch && (sample.getWidth() != actual.getWidth() || sample.getHeight() != actual.getHeight())) {
            result.sizeMismatch = true;
            return result;
        }

        List<Rectangle> ignoreRegions = shot.ignored;

        ComparisonOptions options = new ComparisonOptions();
        options.setTolerance(tolerance);
        options.setAnalyzeOffset(analyzeOffset);
        options.setStretchToFit(stretch);
        options.setIgnoreRegions(ignoreRegions);

        ImageCompareResult comparison = Rainbow4J.compare(screenshot, sample, area,
                new Rectangle(0, 0, sample.getWidth(), sample.getHeight()), options);

        result.percentage = comparison.getPercentage();
        result.pixels = comparison.getTotalPixels();
        result.offsetX = comparison.getOffsetX();
        result.offsetY = comparison.getOffsetY();
        result.heatmapPath = write(heatmap(actual, comparison.getComparisonMap()), new File(outputDir, "heatmap.png"));
        return result;
    }

    /**
     * Draws the actual image dimmed in grey and paints every mismatching pixel on top of it with the colour
     * Rainbow4J assigned (green = small, yellow = medium, red = large difference). Ignored regions are tinted
     * blue and a red frame is drawn around the area that contains differences.
     */
    static BufferedImage heatmap(BufferedImage actual, BufferedImage map) {
        int width = Math.min(actual.getWidth(), map.getWidth());
        int height = Math.min(actual.getHeight(), map.getHeight());
        BufferedImage out = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);

        int minX = Integer.MAX_VALUE, minY = Integer.MAX_VALUE, maxX = -1, maxY = -1;
        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                int rgb = actual.getRGB(x, y);
                int grey = (((rgb >> 16) & 0xff) + ((rgb >> 8) & 0xff) + (rgb & 0xff)) / 3;
                int dim = 40 + grey * 45 / 100;

                int m = map.getRGB(x, y);
                int alpha = (m >>> 24) & 0xff;
                int mr = (m >> 16) & 0xff, mg = (m >> 8) & 0xff, mb = m & 0xff;

                int pixel;
                if (mr > 0 || mg > 0 || mb > 0) {
                    pixel = (mr << 16) | (mg << 8) | mb;
                    minX = Math.min(minX, x);
                    minY = Math.min(minY, y);
                    maxX = Math.max(maxX, x);
                    maxY = Math.max(maxY, y);
                } else if (alpha < 255) {
                    pixel = (dim / 2 << 16) | (dim / 2 << 8) | Math.min(255, dim + 90);
                } else {
                    pixel = (dim << 16) | (dim << 8) | dim;
                }
                out.setRGB(x, y, pixel);
            }
        }

        if (maxX >= 0) {
            Graphics2D g = out.createGraphics();
            g.setColor(new Color(255, 40, 40));
            g.setStroke(new BasicStroke(2));
            int pad = 3;
            g.drawRect(Math.max(0, minX - pad), Math.max(0, minY - pad),
                    Math.min(width - 1, maxX + pad) - Math.max(0, minX - pad),
                    Math.min(height - 1, maxY + pad) - Math.max(0, minY - pad));
            g.dispose();
        }
        return out;
    }

    private static final class Shot {
        BufferedImage image;
        /** Area of the element in screenshot coordinates. */
        Rectangle area;
        /** Ignored regions in screenshot coordinates. */
        List<Rectangle> ignored = new ArrayList<>();
    }

    /**
     * Takes the screenshot for {@code locator}. Unless it is stitched, the element is scrolled into view when
     * it is mostly hidden, by the window or by a scrolling container such as a {@code div} with
     * {@code overflow: auto}; it is then measured again. The element and the ignored regions are moved from
     * document to screenshot coordinates. The original scroll positions are restored afterwards.
     */
    private Shot screenshot(LocatorDto locator, List<LocatorDto> ignore) {
        Rect rect = documentArea(locator);
        long[] original = scrollState();
        long[] state = original;
        // A full page screenshot is made by scrolling and stitching, which repeats sticky and fixed
        // elements. An element that fits in the window is therefore scrolled into view instead.
        boolean stitch = fullPage
                && (!isElement(locator) || rect.getWidth() > state[2] || rect.getHeight() > state[3]);
        GalenConfig.getConfig().setProperty(GalenProperty.SCREENSHOT_FULLPAGE, Boolean.toString(stitch));
        boolean scrolled = stitch;
        try {
            if (!stitch && isElement(locator) && visibleFraction(webElement(locator)) < 0.5) {
                ((JavascriptExecutor) driver).executeScript(SCROLL_INTO_VIEW, webElement(locator));
                scrolled = true;
                // Scrolling a container moves the element within the document, not only within the window
                rect = documentArea(locator);
                state = scrollState();
            }
            int offsetX = stitch ? 0 : (int) state[0];
            int offsetY = stitch ? 0 : (int) state[1];

            Shot shot = new Shot();
            shot.image = page.getScreenshotImage();
            // Galen's viewport object is already in window coordinates
            shot.area = clip(locator, isElement(locator) ? move(rect, offsetX, offsetY) : rect, shot.image);
            if (ignore != null) {
                for (LocatorDto ignoreLocator : ignore) {
                    for (PageElement element : findAll(ignoreLocator)) {
                        if (element.isPresent() && element.isVisible()) {
                            shot.ignored.add(move(element.getArea(), offsetX, offsetY).toAwtRectangle());
                        }
                    }
                }
            }
            return shot;
        } finally {
            if (scrolled) {
                ((JavascriptExecutor) driver).executeScript(RESTORE_SCROLL, original[0], original[1]);
            }
        }
    }

    private static Rect move(Rect rect, int dx, int dy) {
        return new Rect(rect.getLeft() - dx, rect.getTop() - dy, rect.getWidth(), rect.getHeight());
    }

    /** {@code [scrollX, scrollY, innerWidth, innerHeight]} of the window. */
    private long[] scrollState() {
        List<?> values = (List<?>) ((JavascriptExecutor) driver).executeScript(
                "return [Math.round(window.pageXOffset), Math.round(window.pageYOffset), "
                        + "window.innerWidth, window.innerHeight];");
        long[] state = new long[4];
        for (int i = 0; i < 4; i++) {
            state[i] = ((Number) values.get(i)).longValue();
        }
        return state;
    }

    private static boolean isElement(LocatorDto locator) {
        return !VIEWPORT.equals(locator.type) && !SCREEN.equals(locator.type);
    }

    /**
     * Fraction (0-1) of {@code element} that can be seen: inside the window and inside the visible part of
     * every ancestor that clips its content ({@code overflow} other than {@code visible}).
     */
    private double visibleFraction(WebElement element) {
        Object fraction = ((JavascriptExecutor) driver).executeScript(
                "var el = arguments[0], r = el.getBoundingClientRect();"
                        + "var left = Math.max(r.left, 0), top = Math.max(r.top, 0);"
                        + "var right = Math.min(r.right, window.innerWidth), bottom = Math.min(r.bottom, window.innerHeight);"
                        + "for (var n = el.parentElement; n && n !== document.body && n !== document.documentElement;"
                        + "        n = n.parentElement) {"
                        + "  var s = getComputedStyle(n);"
                        + "  if (s.overflowX === 'visible' && s.overflowY === 'visible') continue;"
                        + "  var c = n.getBoundingClientRect();"
                        + "  var cl = c.left + n.clientLeft, ct = c.top + n.clientTop;"
                        + "  left = Math.max(left, cl); top = Math.max(top, ct);"
                        + "  right = Math.min(right, cl + n.clientWidth); bottom = Math.min(bottom, ct + n.clientHeight);"
                        + "}"
                        + "var full = Math.max(1, r.width) * Math.max(1, r.height);"
                        + "return right > left && bottom > top ? (right - left) * (bottom - top) / full : 0;",
                element);
        return ((Number) fraction).doubleValue();
    }

    /**
     * Remembers the scroll position of every scrolled or scrollable ancestor of {@code arguments[0]}, then
     * scrolls it into view. Scrolls the window and any containers in between.
     */
    private static final String SCROLL_INTO_VIEW =
            "var el = arguments[0], saved = [];"
                    + "for (var n = el.parentElement; n; n = n.parentElement) {"
                    + "  if (n.scrollTop || n.scrollLeft || n.scrollHeight > n.clientHeight || n.scrollWidth > n.clientWidth) {"
                    + "    saved.push([n, n.scrollLeft, n.scrollTop]);"
                    + "  }"
                    + "}"
                    + "window.__galenSavedScroll = saved;"
                    + "el.scrollIntoView({block: 'center', inline: 'nearest'});";

    /** Restores the containers saved by {@link #SCROLL_INTO_VIEW} and the window ({@code arguments[0..1]}). */
    private static final String RESTORE_SCROLL =
            "(window.__galenSavedScroll || []).forEach(function (s) { s[0].scrollLeft = s[1]; s[0].scrollTop = s[2]; });"
                    + "delete window.__galenSavedScroll;"
                    + "window.scrollTo(arguments[0], arguments[1]);";

    private WebElement webElement(LocatorDto locator) {
        return ((WebPageElement) page.getObject(toLocator(locator))).getWebElement();
    }

    /** Area of {@code locator} in document coordinates. */
    private Rect documentArea(LocatorDto locator) {
        if (!isElement(locator)) {
            return page.getSpecialObject(locator.type).getArea();
        }
        PageElement element = page.getObject(toLocator(locator));
        if (element == null || !element.isPresent()) {
            throw new IllegalArgumentException("Element not found: " + locator.type + ":" + locator.value);
        }
        if (!element.isVisible()) {
            throw new IllegalArgumentException("Element is not visible: " + locator.type + ":" + locator.value);
        }
        return element.getArea();
    }

    /** Clips {@code rect} (screenshot coordinates) to the screenshot; fails when most of it is outside. */
    private static Rectangle clip(LocatorDto locator, Rect rect, BufferedImage screenshot) {
        int x = Math.max(0, rect.getLeft());
        int y = Math.max(0, rect.getTop());
        int right = Math.min(screenshot.getWidth(), rect.getLeft() + rect.getWidth());
        int bottom = Math.min(screenshot.getHeight(), rect.getTop() + rect.getHeight());
        int width = right - x;
        int height = bottom - y;

        long full = (long) Math.max(1, rect.getWidth()) * Math.max(1, rect.getHeight());
        if (width <= 0 || height <= 0 || (double) width * height / full < 0.5) {
            throw new IllegalArgumentException(String.format(
                    "Element is (mostly) outside of the screenshot (element x=%d y=%d w=%d h=%d, screenshot %dx%d). "
                            + "Scroll it into view or use full_page=True.",
                    rect.getLeft(), rect.getTop(), rect.getWidth(), rect.getHeight(),
                    screenshot.getWidth(), screenshot.getHeight()));
        }
        return new Rectangle(x, y, width, height);
    }

    private List<PageElement> findAll(LocatorDto dto) {
        List<PageElement> elements = new ArrayList<>();
        Locator locator = toLocator(dto);
        int count = page.getObjectCount(locator);
        for (int i = 1; i <= count; i++) {
            elements.add(page.getObject(new Locator(locator.getLocatorType(), locator.getLocatorValue(), i)));
        }
        return elements;
    }

    static Locator toLocator(LocatorDto dto) {
        if ("id".equals(dto.type)) {
            return Locator.id(dto.value);
        } else if ("xpath".equals(dto.type)) {
            return Locator.xpath(dto.value);
        } else if ("css".equals(dto.type)) {
            return Locator.css(dto.value);
        }
        throw new IllegalArgumentException("Unsupported locator type: " + dto.type);
    }

    private static BufferedImage copy(BufferedImage image) {
        BufferedImage copy = new BufferedImage(image.getWidth(), image.getHeight(), BufferedImage.TYPE_INT_ARGB);
        Graphics2D g = copy.createGraphics();
        g.drawImage(image, 0, 0, null);
        g.dispose();
        return copy;
    }

    private static String write(BufferedImage image, File file) throws IOException {
        if (file.getParentFile() != null) {
            file.getParentFile().mkdirs();
        }
        Rainbow4J.saveImage(image, file);
        return file.getAbsolutePath();
    }
}
