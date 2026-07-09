import 'package:flutter_test/flutter_test.dart';
import 'package:app_recaudo_legal/utils/client_list_pagination.dart';

void main() {
  group('ClientListPagination', () {
    test('slice returns first page', () {
      final p = ClientListPagination(pageSize: 10);
      final items = List.generate(25, (i) => i);
      final page = p.slice(items);
      expect(page.length, 10);
      expect(page.first, 0);
      expect(page.last, 9);
    });

    test('next and previous navigate pages', () {
      final p = ClientListPagination(pageSize: 10);
      p.syncTotal(25);
      expect(p.totalPages, 3);
      p.next();
      expect(p.page, 1);
      p.next();
      expect(p.page, 2);
      p.next();
      expect(p.page, 2);
      p.previous();
      expect(p.page, 1);
    });

    test('reset returns to first page', () {
      final p = ClientListPagination(pageSize: 5);
      p.syncTotal(20);
      p.goTo(2);
      p.reset();
      expect(p.page, 0);
    });

    test('syncTotal clamps page when list shrinks', () {
      final p = ClientListPagination(pageSize: 10);
      p.syncTotal(50);
      p.goTo(4);
      p.syncTotal(15);
      expect(p.page, 1);
      expect(p.totalPages, 2);
    });

    test('needsBar is false for small lists', () {
      final p = ClientListPagination(pageSize: 30);
      p.syncTotal(10);
      expect(p.needsBar, isFalse);
      p.syncTotal(31);
      expect(p.needsBar, isTrue);
    });
  });
}
