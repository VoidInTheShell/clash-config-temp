// SublinkPro filterNode script for metadata-only Mihomo node names.
// Final NodeNameRule: $Name$LinkCountryName $LinkName

var INFO_NODE_PATTERN = /(?:剩余流量|套餐到期|距离下次重置|下次重置|重置剩余|到期时间|有效期|流量重置|防失联|官网|traffic\s*left|expire|reset|website)/i;
var RATE_PATTERN = /(?:\d+(?:\.\d+)?\s*(?:[xX×]|倍(?:率)?)|(?:[xX×])\s*\d+(?:\.\d+)?)/;

// Used only when LinkCountry is empty. These mirror the regions currently
// present in this subscription without carrying airport routing semantics.
var COUNTRY_NAME_FALLBACKS = [
    { code: 'HK', pattern: /(?:香港|hong\s*kong|(?:^|[^a-z])HK(?:[^a-z]|$))/i },
    { code: 'TW', pattern: /(?:台湾|臺灣|taiwan|(?:^|[^a-z])TW(?:[^a-z]|$))/i },
    { code: 'JP', pattern: /(?:日本|东京|大阪|japan|tokyo|osaka|(?:^|[^a-z])JP(?:[^a-z]|$))/i },
    { code: 'SG', pattern: /(?:新加坡|狮城|singapore|(?:^|[^a-z])SG(?:[^a-z]|$))/i },
    { code: 'US', pattern: /(?:美国|洛杉矶|纽约|西雅图|united\s*states|los\s*angeles|new\s*york|seattle|USA|(?:^|[^a-z])US(?:[^a-z]|$))/i },
    { code: 'KR', pattern: /(?:韩国|首尔|korea|seoul|(?:^|[^a-z])KR(?:[^a-z]|$))/i },
    { code: 'MY', pattern: /(?:马来西亚|malaysia|(?:^|[^a-z])MY(?:[^a-z]|$))/i },
    { code: 'IN', pattern: /(?:印度|孟买|india|mumbai|(?:^|[^a-z])IN(?:[^a-z]|$))/i },
    { code: 'GB', pattern: /(?:英国|伦敦|united\s*kingdom|london|(?:^|[^a-z])(?:GB|UK)(?:[^a-z]|$))/i },
    { code: 'TR', pattern: /(?:土耳其|turkey|(?:^|[^a-z])TR(?:[^a-z]|$))/i },
    { code: 'AU', pattern: /(?:澳大利亚|澳洲|悉尼|墨尔本|australia|sydney|melbourne|(?:^|[^a-z])AU(?:[^a-z]|$))/i }
];

var AI_PROVIDERS = [
    { key: 'claude', label: 'Claude' },
    { key: 'gemini', label: 'Gemini' },
    { key: 'openai', label: 'OpenAI' }
];

var STREAMING_PROVIDERS = [
    { key: 'netflix', label: 'Netflix' },
    { key: 'disney', label: 'Disney+' },
    { key: 'youtube_premium', label: 'YouTube Premium' },
    { key: 'bahamut', label: 'Bahamut' }
];

// Match the template's primary region order; remaining country codes sort A-Z.
var HOME_COUNTRY_PRIORITY = ['US', 'HK', 'SG', 'JP', 'TW'];
var SELF_GROUPS = ['自建节点', '自建选1', '自建选2', '自建选3'];

function normalizeProvider(value) {
    return String(value || '')
        .toLowerCase()
        .replace(/[\s-]+/g, '_')
        .replace(/^_+|_+$/g, '');
}

function availableProviders(rawSummary) {
    var available = {};
    if (!rawSummary) {
        return available;
    }

    try {
        var summary = JSON.parse(rawSummary);
        var providers = summary && Array.isArray(summary.providers) ? summary.providers : [];
        providers.forEach(function (item) {
            if (String(item.status || '').toLowerCase() === 'available') {
                available[normalizeProvider(item.provider)] = true;
            }
        });
    } catch (error) {
        console.warn('Unable to parse UnlockSummary for node rename');
    }

    return available;
}

function regionalIndicator(letter) {
    var codePoint = 0x1F1E6 + letter.charCodeAt(0) - 65 - 0x10000;
    return String.fromCharCode(
        0xD800 + (codePoint >> 10),
        0xDC00 + (codePoint & 0x3FF)
    );
}

function countryCodeFromFlag(value) {
    var text = String(value || '');
    for (var index = 0; index + 3 < text.length; index += 1) {
        var high1 = text.charCodeAt(index);
        var low1 = text.charCodeAt(index + 1);
        var high2 = text.charCodeAt(index + 2);
        var low2 = text.charCodeAt(index + 3);
        if (
            high1 === 0xD83C && low1 >= 0xDDE6 && low1 <= 0xDDFF &&
            high2 === 0xD83C && low2 >= 0xDDE6 && low2 <= 0xDDFF
        ) {
            return String.fromCharCode(65 + low1 - 0xDDE6, 65 + low2 - 0xDDE6);
        }
    }
    return '';
}

function fallbackCountryFromName(linkName) {
    var text = String(linkName || '');
    var flagCountry = countryCodeFromFlag(text);
    if (flagCountry) {
        return flagCountry;
    }

    for (var index = 0; index < COUNTRY_NAME_FALLBACKS.length; index += 1) {
        if (COUNTRY_NAME_FALLBACKS[index].pattern.test(text)) {
            return COUNTRY_NAME_FALLBACKS[index].code;
        }
    }
    return '';
}

function resolvedCountry(node) {
    var detected = String(node.LinkCountry || '').trim().toUpperCase();
    if (/^[A-Z]{2}$/.test(detected)) {
        return detected;
    }
    return fallbackCountryFromName(node.LinkName || node.Name || '');
}

function countryNamePrefix(countryCode) {
    var code = String(countryCode || '').toUpperCase();
    if (!/^[A-Z]{2}$/.test(code)) {
        return '🏳️ ';
    }

    var flag = regionalIndicator(code.charAt(0)) + regionalIndicator(code.charAt(1));
    // $LinkCountryName currently resolves TW to 台湾. Prefix 中国 only for TW.
    return flag + (code === 'TW' ? ' 中国' : ' ');
}

function originalRate(linkName) {
    var match = String(linkName || '').match(RATE_PATTERN);
    return match ? match[0].trim() : '';
}

function isInfoNode(node) {
    return INFO_NODE_PATTERN.test(String(node.LinkName || node.Name || ''));
}

function isConfirmedResidential(node) {
    return String(node.QualityStatus || '').toLowerCase() === 'success' && node.IsResidential === true;
}

function buildVisibleTags(node, available) {
    var tags = [];

    if (isConfirmedResidential(node)) {
        tags.push('家宽');
    }

    var rate = originalRate(node.LinkName);
    if (rate) {
        tags.push(rate);
    }

    available = available || availableProviders(node.UnlockSummary);
    var allAI = AI_PROVIDERS.every(function (provider) {
        return available[provider.key] === true;
    });

    if (allAI) {
        tags.push('AI');
    } else {
        AI_PROVIDERS.forEach(function (provider) {
            if (available[provider.key] === true) {
                tags.push(provider.label);
            }
        });
    }

    STREAMING_PROVIDERS.forEach(function (provider) {
        if (available[provider.key] === true) {
            tags.push(provider.label);
        }
    });

    return tags;
}

function providerCount(available, providers) {
    return providers.reduce(function (count, provider) {
        return count + (available[provider.key] === true ? 1 : 0);
    }, 0);
}

function compareProviderAvailability(left, right, providers) {
    for (var index = 0; index < providers.length; index += 1) {
        var key = providers[index].key;
        if (left[key] !== right[key]) {
            return left[key] === true ? -1 : 1;
        }
    }
    return 0;
}

function compareHomeCountry(leftCode, rightCode) {
    var leftPriority = HOME_COUNTRY_PRIORITY.indexOf(leftCode);
    var rightPriority = HOME_COUNTRY_PRIORITY.indexOf(rightCode);
    var leftKnown = leftPriority !== -1;
    var rightKnown = rightPriority !== -1;

    if (leftKnown || rightKnown) {
        if (leftKnown && rightKnown) {
            return leftPriority - rightPriority;
        }
        return leftKnown ? -1 : 1;
    }
    if (!leftCode || !rightCode) {
        return leftCode ? -1 : rightCode ? 1 : 0;
    }
    return leftCode < rightCode ? -1 : leftCode > rightCode ? 1 : 0;
}

function compareHomeItems(left, right) {
    var countryOrder = compareHomeCountry(left.countryCode, right.countryCode);
    if (countryOrder !== 0) {
        return countryOrder;
    }

    var leftAllAI = AI_PROVIDERS.every(function (provider) {
        return left.available[provider.key] === true;
    });
    var rightAllAI = AI_PROVIDERS.every(function (provider) {
        return right.available[provider.key] === true;
    });
    if (leftAllAI !== rightAllAI) {
        return leftAllAI ? -1 : 1;
    }

    var aiCountOrder = providerCount(right.available, AI_PROVIDERS) - providerCount(left.available, AI_PROVIDERS);
    if (aiCountOrder !== 0) {
        return aiCountOrder;
    }

    var streamingCountOrder = providerCount(right.available, STREAMING_PROVIDERS) - providerCount(left.available, STREAMING_PROVIDERS);
    if (streamingCountOrder !== 0) {
        return streamingCountOrder;
    }

    var aiProviderOrder = compareProviderAvailability(left.available, right.available, AI_PROVIDERS);
    if (aiProviderOrder !== 0) {
        return aiProviderOrder;
    }

    var streamingProviderOrder = compareProviderAvailability(left.available, right.available, STREAMING_PROVIDERS);
    return streamingProviderOrder !== 0 ? streamingProviderOrder : left.originalIndex - right.originalIndex;
}

function sortResidentialSlots(prepared) {
    var sortedResidential = prepared
        .filter(function (item) {
            return item.residential;
        })
        .sort(compareHomeItems);
    var residentialIndex = 0;

    return prepared.map(function (item) {
        if (!item.residential) {
            return item;
        }
        var replacement = sortedResidential[residentialIndex];
        residentialIndex += 1;
        return replacement;
    });
}

function isSelfBuilt(node) {
    return String(node.Group || '').trim().indexOf('自建') === 0;
}

function originalSelfName(node) {
    var mode = String(node.NameMode || '').toLowerCase();
    if ((mode === 'remark' || mode === 'custom') && String(node.Name || '').trim()) {
        return String(node.Name);
    }
    return String(node.LinkName || node.Name || '');
}

// filterNode and subMod execute in separate Goja runtimes. Carry the original
// name through the subscription-wide name rule, then restore it in subMod.
var SELF_NAME_PREFIX = '__SUBLINK_SELF_NAME_';
var SELF_NAME_SUFFIX = '__END_SELF_NAME__';

function filterNode(nodes, clientType) {
    var prepared = nodes
        .filter(function (node) {
            return isSelfBuilt(node) || !isInfoNode(node);
        })
        .map(function (node, originalIndex) {
            if (isSelfBuilt(node)) {
                return { node: node, selfName: originalSelfName(node), residential: false };
            }
            var countryCode = resolvedCountry(node);
            var available = availableProviders(node.UnlockSummary);
            var tags = buildVisibleTags(node, available);
            node.LinkCountry = countryCode;
            return {
                node: node,
                tags: tags,
                countryCode: countryCode,
                available: available,
                residential: isConfirmedResidential(node),
                originalIndex: originalIndex,
                collisionKey: countryCode + '|' + tags.join(' ')
            };
        });

    prepared = sortResidentialSlots(prepared);

    var totals = {};
    prepared.forEach(function (item) {
        if (item.selfName === undefined) totals[item.collisionKey] = (totals[item.collisionKey] || 0) + 1;
    });

    var indexes = {};
    return prepared.map(function (item) {
        var node = item.node;
        if (item.selfName !== undefined) {
            var carried = SELF_NAME_PREFIX + encodeURIComponent(item.selfName) + SELF_NAME_SUFFIX;
            node.Name = carried;
            node.LinkName = carried;
            return node;
        }
        var tags = item.tags.slice();
        indexes[item.collisionKey] = (indexes[item.collisionKey] || 0) + 1;

        if (totals[item.collisionKey] > 1) {
            tags.push('#' + indexes[item.collisionKey]);
        }

        // Do not retain the airport-defined node name in either exported name variable.
        node.Name = countryNamePrefix(node.LinkCountry);
        node.LinkName = tags.join(' ');
        return node;
    });
}

function findYamlSection(lines, key) {
    var start = -1;
    for (var index = 0; index < lines.length; index += 1) {
        if (lines[index] === key + ':') {
            start = index;
            break;
        }
    }
    if (start === -1) {
        return null;
    }

    var end = lines.length;
    for (var lineIndex = start + 1; lineIndex < lines.length; lineIndex += 1) {
        if (/^[^\s#-][^:]*:/.test(lines[lineIndex])) {
            end = lineIndex;
            break;
        }
    }
    return { start: start, end: end };
}

function extractHomeProxyScalars(lines, selfProxyScalars) {
    var section = findYamlSection(lines, 'proxies');
    if (!section) {
        return [];
    }

    var names = [];
    for (var index = section.start + 1; index < section.end; index += 1) {
        var match = lines[index].match(/^\s*-\s+name:\s*(.+?)\s*$/);
        // Keep the original YAML scalar for output; quotes are not part of a tag.
        var name = match ? match[1].replace(/^["']|["']$/g, '') : '';
        if (match && /(?:^| )家宽(?: |#|$)/.test(name) && (selfProxyScalars || []).indexOf(match[1]) === -1) {
            names.push(match[1]);
        }
    }
    return names;
}

function replaceManagedGroup(lines, proxyScalars, groupName, icon) {
    var section = findYamlSection(lines, 'proxy-groups');
    if (!section || proxyScalars.length === 0) {
        return lines;
    }

    var itemIndent = null;
    for (var index = section.start + 1; index < section.end; index += 1) {
        var itemMatch = lines[index].match(/^(\s*)-\s+/);
        if (itemMatch && (itemIndent === null || itemMatch[1].length < itemIndent)) {
            itemIndent = itemMatch[1].length;
        }
    }
    if (itemIndent === null) {
        return lines;
    }

    var itemStarts = [];
    for (var lineIndex = section.start + 1; lineIndex < section.end; lineIndex += 1) {
        var startMatch = lines[lineIndex].match(/^(\s*)-\s+/);
        if (startMatch && startMatch[1].length === itemIndent) {
            itemStarts.push(lineIndex);
        }
    }

    var targetStart = -1;
    var targetEnd = -1;
    for (var itemIndex = 0; itemIndex < itemStarts.length; itemIndex += 1) {
        var blockStart = itemStarts[itemIndex];
        var blockEnd = itemIndex + 1 < itemStarts.length ? itemStarts[itemIndex + 1] : section.end;
        for (var blockIndex = blockStart; blockIndex < blockEnd; blockIndex += 1) {
            var groupMatch = lines[blockIndex].match(/^\s*(?:-\s*)?name:\s*(.+?)\s*$/);
            if (groupMatch && yamlScalar(groupMatch[1]) === groupName) {
                targetStart = blockStart;
                targetEnd = blockEnd;
                break;
            }
        }
        if (targetStart !== -1) {
            break;
        }
    }
    if (targetStart === -1) {
        return lines;
    }

    var itemPrefix = new Array(itemIndent + 1).join(' ');
    var fieldPrefix = itemPrefix + '  ';
    var memberPrefix = fieldPrefix + '  ';
    var replacement = [
        itemPrefix + '- name: ' + groupName,
        fieldPrefix + 'type: select',
        fieldPrefix + 'proxies:'
    ];
    proxyScalars.forEach(function (scalar) {
        replacement.push(memberPrefix + '- ' + scalar);
    });
    // Keep the independent self-built selectors when materializing home nodes.
    if (groupName === '家宽手选') {
        SELF_GROUPS.slice(1).forEach(function (name) {
            replacement.push(memberPrefix + '- ' + name);
        });
    }
    replacement.push(fieldPrefix + 'icon: ' + icon);

    return lines.slice(0, targetStart).concat(replacement, lines.slice(targetEnd));
}

function yamlScalar(value) {
    value = String(value).trim();
    if (value.charAt(0) === '"') {
        // Go's YAML encoder uses \UXXXXXXXX for emoji; JSON only accepts \uXXXX.
        var extraEscapes = { '0': 0, a: 7, v: 11, e: 27, ' ': 32, N: 133, _: 160, L: 8232, P: 8233 };
        return JSON.parse(value.replace(/\\(U[0-9a-fA-F]{8}|x[0-9a-fA-F]{2}|.)/g, function (whole, escape) {
            var code = escape.charAt(0) === 'U' || escape.charAt(0) === 'x'
                ? parseInt(escape.slice(1), 16) : extraEscapes[escape];
            if (code === undefined) return whole;
            var decoded = code <= 65535 ? String.fromCharCode(code)
                : String.fromCharCode(55296 + ((code - 65536) >> 10), 56320 + ((code - 65536) & 1023));
            return JSON.stringify(decoded).slice(1, -1);
        }));
    }
    if (value.charAt(0) === "'") return value.slice(1, -1).replace(/''/g, "'");
    return value;
}

function regexLiteral(value) {
    return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function restoreSelfNames(lines) {
    var section = findYamlSection(lines, 'proxies');
    var scalars = [];
    var marker = new RegExp(SELF_NAME_PREFIX + '(.*?)' + SELF_NAME_SUFFIX);
    for (var index = 0; index < lines.length; index += 1) {
        var field = lines[index].match(/^(\s*(?:-\s*)?(?:name|dialer-proxy):\s*)(.+)$/);
        if (!field) continue;
        var encoded = field[2].match(marker);
        if (!encoded) continue;
        var scalar = JSON.stringify(decodeURIComponent(encoded[1]));
        lines[index] = field[1] + scalar;
        if (section && index > section.start && index < section.end && /name:/.test(field[1])) {
            scalars.push(scalar);
        }
    }
    return scalars;
}

function existingSelfScalars(lines) {
    var scalars = [];
    var indent = -1;
    var inMembers = false;
    lines.forEach(function (line) {
        var title = line.match(/^(\s*)-\s+name:\s*自建节点\s*$/);
        if (title) { indent = title[1].length; inMembers = false; return; }
        if (indent < 0) return;
        var item = line.match(/^(\s*)-\s+(.+)$/);
        if (item && item[1].length <= indent) { indent = -1; return; }
        if (/^\s*proxies:\s*$/.test(line)) { inMembers = true; return; }
        if (inMembers && item) scalars.push(item[2]);
        else if (inMembers && /\S/.test(line)) inMembers = false;
    });
    return scalars;
}

function excludeSelfNames(lines, scalars) {
    var section = findYamlSection(lines, 'proxy-groups');
    if (!section || scalars.length === 0) return lines;
    var exact = '^(?:' + scalars.map(function (scalar) {
        return regexLiteral(yamlScalar(scalar));
    }).join('|') + ')$';
    // Rendered groups have no aliases. Add an exact-name exclusion to each
    // dynamic group; parent selectors keep referring to the self-built group.
    for (var index = section.end - 1; index > section.start; index -= 1) {
        var include = lines[index].match(/^(\s*)(-\s+)?include-all:\s*true\s*$/);
        if (!include) continue;
        var start = index;
        while (start > section.start && !/^\s*-\s+/.test(lines[start])) start -= 1;
        var end = index + 1;
        while (end < section.end && !/^\s*-\s+/.test(lines[end])) end += 1;
        var found = false;
        for (var cursor = start; cursor < end; cursor += 1) {
            var exclusion = lines[cursor].match(/^(\s*(?:-\s*)?)exclude-filter:\s*(.+)$/);
            if (exclusion) {
                var previous = yamlScalar(exclusion[2]);
                if (previous !== exact && previous.slice(-exact.length - 1) !== '|' + exact) {
                    lines[cursor] = exclusion[1] + 'exclude-filter: ' + JSON.stringify(previous + '|' + exact);
                }
                found = true;
                break;
            }
        }
        var fieldIndent = include[1] + (include[2] ? '  ' : '');
        if (!found) lines.splice(index + 1, 0, fieldIndent + 'exclude-filter: ' + JSON.stringify(exact));
    }
    return lines;
}

// Preserve original self-built names and materialize their membership by source.
// Airport residential nodes retain their sorted, exclusive manual selector.
function subMod(input, clientType) {
    var hadTrailingNewline = /\r?\n$/.test(String(input || ''));
    var lines = String(input || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
    var selfScalars = restoreSelfNames(lines);
    if (selfScalars.length === 0) selfScalars = existingSelfScalars(lines);
    SELF_GROUPS.forEach(function (groupName) {
        lines = replaceManagedGroup(lines, selfScalars, groupName, 'https://testingcf.jsdelivr.net/gh/Koolson/Qure@master/IconSet/Color/Direct.png');
    });
    var homeScalars = extractHomeProxyScalars(lines, selfScalars);
    lines = replaceManagedGroup(lines, homeScalars, '家宽手选', 'https://raw.githubusercontent.com/Mithcell-Ma/icon/refs/heads/main/home.png');
    var output = excludeSelfNames(lines, selfScalars).join('\n');
    return hadTrailingNewline && !/\n$/.test(output) ? output + '\n' : output;
}
